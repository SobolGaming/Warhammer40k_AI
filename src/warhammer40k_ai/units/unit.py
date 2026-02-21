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
from ..utility.attack_roll_parser import AttackRollCondition, AttackRollRule, AttackRollEffect, parse_attack_roll_text
from .status_effects import StatusEffect, BattleShockEffect
from ..utility.entity_ids import get_entity_id, maybe_entity_id
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
    charged_turn: Optional[int] = None
    charged_turn_owner: Optional[str] = None
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
    disembarked_from_transport_id: Optional[str] = None  # Track transport id for disembark-based abilities
    # Mission actions
    performing_action_name: Optional[str] = None
    action_started_turn: Optional[int] = None
    action_completes_turn: Optional[int] = None
    action_locked_until_turn_end: bool = False  # Cannot shoot or declare charge while true (except titanic character rule handled at call site)
    fought_this_phase: bool = False  # Used by timing-sensitive rules (e.g., Total Carnage)
    eligible_to_fight_this_phase: bool = False  # True once the unit is observed as fight-eligible in the current Fight phase.
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


from .unit_mixins import (
    RulesParsingMixin,
    DatasheetWargearMixin,
    DamageDeathMixin,
    StateAttachmentMixin,
    ActionsMovementMixin,
    ShootingMixin,
    PositioningMixin,
    KeywordsDetachmentsMixin,
    AbilitySpecsMixin,
    LateGameplayMixin,
)
from .unit_mixins import (
    rules_parsing_mixin as _rules_parsing_mixin,
    datasheet_wargear_mixin as _datasheet_wargear_mixin,
    damage_death_mixin as _damage_death_mixin,
    state_attachment_mixin as _state_attachment_mixin,
    actions_movement_mixin as _actions_movement_mixin,
    shooting_mixin as _shooting_mixin,
    positioning_mixin as _positioning_mixin,
    keywords_detachments_mixin as _keywords_detachments_mixin,
    ability_specs_mixin as _ability_specs_mixin,
    late_gameplay_mixin as _late_gameplay_mixin,
)

_UNIT_MIXIN_MODULES = (
    _rules_parsing_mixin,
    _datasheet_wargear_mixin,
    _damage_death_mixin,
    _state_attachment_mixin,
    _actions_movement_mixin,
    _shooting_mixin,
    _positioning_mixin,
    _keywords_detachments_mixin,
    _ability_specs_mixin,
    _late_gameplay_mixin,
)

for _mixin_module in _UNIT_MIXIN_MODULES:
    _mixin_module.UnitRoundState = UnitRoundState
    _mixin_module.MovementAction = MovementAction
    _mixin_module.MovementState = MovementState

class Unit(
    RulesParsingMixin,
    DatasheetWargearMixin,
    DamageDeathMixin,
    StateAttachmentMixin,
    ActionsMovementMixin,
    ShootingMixin,
    PositioningMixin,
    KeywordsDetachmentsMixin,
    AbilitySpecsMixin,
    LateGameplayMixin,
):
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
            logger.exception(f"{self.name} - NEED TO HANDLE - ERROR PARSING UNIT COMPOSITION: {e}")
            self.unit_composition = {}
            return
        try:
            self.models_cost = self._parse_models_cost(datasheet.datasheets_models_cost)
        except Exception as e:
            #print(f"{self.name} - NEED TO HANDLE - ERROR PARSING MODELS COST: {e}")
            self.models_cost = { "spawn_on_death": 0 }
        self.models = self._create_models(datasheet, quantity)
        self._initialize_horrors_state()

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
        # Support Artillery: track non-Leader units joined to this unit (e.g., Support Weapon platforms).
        self.attached_support_units: List['Unit'] = []
        # For Support Artillery units: track which unit this model is joined to (if any).
        self.support_joined_to = None

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
        # Ability cache generations:
        # - structure: ability sources/text changed (attach/detach/split/add/remove abilities, etc.)
        # - activity: runtime activation changed while ability text remained the same.
        self._ability_structure_generation = 0
        self._ability_activity_generation = 0
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
        # Parse stratagem-target CP refund abilities (roll D6; gain 1CP).
        try:
            self._refresh_targeted_stratagem_cp_refund_flags()
        except Exception:
            pass
        try:
            self._refresh_targeted_stratagem_cp_increase_flags()
        except Exception:
            pass
        try:
            self._refresh_targeted_stratagem_cp_increase_flags()
        except Exception:
            pass
        # Parse stratagem CP increases applied to enemy targets.
        try:
            self._refresh_targeted_stratagem_cp_increase_flags()
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
        # Parse fixed Advance distance rules that replace the Advance roll.
        try:
            self._refresh_advance_no_roll_flags()
        except Exception:
            pass
        # Parse ignore-vertical-distance move type rules.
        try:
            self._refresh_ignore_vertical_distance_move_types()
        except Exception:
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

    def _collect_characteristic_modifiers(
        self,
        model: Model,
        ckey: str,
        *,
        base_val: int,
        base_raw=None,
        game_map=None,
    ):
        from ..utility.modifiers import Modifier, ModifierOp

        mods = []
        objective_control_floor = 0

        # Engine-registered modifiers (from enhancements, damaged profiles, status effects, etc.)
        try:
            mods.extend(list((self._characteristic_modifiers or {}).get(ckey, []) or []))
        except Exception:
            pass

        def _enhancement_bearer_is_leading(rule_key: str) -> bool:
            try:
                root_unit = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
            except Exception:
                root_unit = self
            leaders = list(getattr(root_unit, "attached_leaders", []) or [])
            for leader in leaders:
                if leader is None:
                    continue
                sr_leader = getattr(leader, "special_rules", None)
                if not isinstance(sr_leader, dict) or not sr_leader.get(rule_key):
                    continue
                bearer_id = str(sr_leader.get("enhancement_bearer_model_id", "") or "")
                if not bearer_id:
                    continue
                for lm in list(getattr(leader, "models", []) or []):
                    if not getattr(lm, "is_alive", True):
                        continue
                    if str(get_entity_id(lm) or "") == bearer_id:
                        return True
            return False

        # Eager to Prove (Slaanesh's Chosen): while the bearer's unit is Favoured Champions,
        # add to the Move characteristic of models in that unit.
        if ckey == "movement":
            try:
                root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
            except Exception:
                root = self
            try:
                army = root.get_parent_army() if root is not None else None
            except Exception:
                army = None
            try:
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is None and army is not None:
                    mgr = getattr(army, "emperors_children_detachments", None)
            except Exception:
                mgr = None
            if mgr is not None and bool(getattr(mgr, "is_favoured_champions", lambda _u: False)(root)):
                has_eager = False
                try:
                    checker = getattr(root, "_attached_unit_has_active_enhancement", None)
                    if callable(checker):
                        has_eager = bool(
                            checker(
                                "enhancement_eager_to_prove",
                                enhancement_id="000010018002",
                                enhancement_name="eager to prove",
                            )
                        )
                except Exception:
                    has_eager = False
                if has_eager:
                    bonus = 0
                    try:
                        members = list(root.get_attached_unit_members() or [])
                    except Exception:
                        members = [root]
                    if not members:
                        members = [root]
                    for member in members:
                        sr_member = getattr(member, "special_rules", None)
                        if not isinstance(sr_member, dict):
                            continue
                        if not sr_member.get("enhancement_eager_to_prove"):
                            continue
                        try:
                            bonus = max(
                                bonus,
                                int(sr_member.get("enhancement_eager_to_prove_favoured_move_bonus", 2) or 2),
                            )
                        except Exception:
                            continue
                    if bonus:
                        mods.append(Modifier(ModifierOp.ADD, int(bonus), source="enhancement:eager_to_prove_favoured"))

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
                            if re.search(r"add\s+1\s+to\s+the\s+objective\s+control\s+characteristic", desc, flags=re.IGNORECASE):
                                mods.append(Modifier(ModifierOp.ADD, 1, source="ability:leading_oc_add_1"))
                except Exception:
                    continue

            # Inspiring Commander: while included in your army, named units gain
            # a fixed Objective Control value for non-CHARACTER models while not Battle-shocked.
            try:
                root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
            except Exception:
                root = self
            try:
                unit_name = str(getattr(root, "name", "") or getattr(self, "name", "") or "")
            except Exception:
                unit_name = str(getattr(self, "name", "") or "")
            normalize_name = getattr(root, "normalize_unit_name_for_rules", None)
            if not callable(normalize_name):
                normalize_name = getattr(self, "normalize_unit_name_for_rules", None)
            if callable(normalize_name):
                recipient_unit_key = str(normalize_name(unit_name) or "").strip()
            else:
                recipient_unit_key = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", unit_name.lower())).strip()
            if recipient_unit_key and not self.is_battle_shocked():
                is_character_model = False
                try:
                    is_character_model = bool(getattr(model, "is_character", False))
                except Exception:
                    is_character_model = False
                if not is_character_model:
                    try:
                        has_any = getattr(model, "has_any_keyword", None)
                        if callable(has_any):
                            is_character_model = bool(has_any("CHARACTER"))
                    except Exception:
                        pass
                if not is_character_model:
                    try:
                        army = root.get_parent_army() if root is not None else self.get_parent_army()
                    except Exception:
                        army = None
                    try:
                        army_units = list(getattr(army, "units", []) or []) if army is not None else []
                    except Exception:
                        army_units = []
                    for source_unit in army_units:
                        if source_unit is None:
                            continue
                        get_specs = getattr(source_unit, "get_inspiring_commander_specs", None)
                        if not callable(get_specs):
                            continue
                        for spec in list(get_specs() or []):
                            try:
                                target_keys = [str(v or "") for v in list(spec.get("target_unit_keys") or [])]
                            except Exception:
                                target_keys = []
                            if recipient_unit_key not in target_keys:
                                continue
                            try:
                                set_value = int(spec.get("objective_control"))
                            except (TypeError, ValueError):
                                continue
                            source_name = str(spec.get("source") or "Inspiring Commander").strip() or "Inspiring Commander"
                            mods.append(
                                Modifier(
                                    ModifierOp.SET,
                                    int(set_value),
                                    source=f"ability:inspiring_commander:{source_name}",
                                )
                            )

            # Strategic Savant (Aspect Host): +1 OC while leading Aspect Warriors.
            try:
                root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
            except Exception:
                root = self
            try:
                leaders = list(getattr(root, "attached_leaders", []) or [])
            except Exception:
                leaders = []
            if leaders:
                try:
                    from ..utility.keyword_utils import unit_has_keyword
                    is_aspect = unit_has_keyword(root, "ASPECT WARRIORS")
                except Exception:
                    is_aspect = False
                if is_aspect:
                    for leader in leaders:
                        sr = getattr(leader, "special_rules", None)
                        if not isinstance(sr, dict):
                            continue
                        if sr.get("enhancement_strategic_savant"):
                            mods.append(Modifier(ModifierOp.ADD, 1, source="enhancement:strategic_savant"))
                            break

            # Craftworld's Champion (Guardian Battlehost): bearer has Objective Control 5.
            try:
                root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
            except Exception:
                root = self
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            if not members:
                members = [root]
            model_id = str(maybe_entity_id(model) or "")
            if model_id:
                for member in members:
                    sr_member = getattr(member, "special_rules", None)
                    if not isinstance(sr_member, dict):
                        continue
                    if not sr_member.get("enhancement_craftworlds_champion"):
                        continue
                    bearer_id = str(sr_member.get("enhancement_bearer_model_id", "") or "")
                    if bearer_id:
                        if bearer_id != model_id:
                            continue
                    else:
                        get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                        bearer = get_bearer() if callable(get_bearer) else None
                        if str(maybe_entity_id(bearer) or "") != model_id:
                            continue
                    try:
                        oc_value = int(sr_member.get("enhancement_craftworlds_champion_objective_control", 5) or 5)
                    except Exception:
                        oc_value = 5
                    mods.append(Modifier(ModifierOp.SET, int(max(1, oc_value)), source="enhancement:craftworlds_champion"))
                    break

            # Mandulian Reliquary (Warpbane Task Force): while the bearer's unit is not
            # Battle-shocked, add 3 to the bearer's Objective Control characteristic.
            try:
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and sr.get("enhancement_mandulian_reliquary"):
                    bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
                    model_id = str(get_entity_id(model) or "")
                    if bearer_id and model_id and bearer_id == model_id and not root.is_battle_shocked():
                        mods.append(Modifier(ModifierOp.ADD, 3, source="enhancement:mandulian_reliquary"))
            except Exception:
                pass

            # Strategic Conqueror (Mont'ka): +1 OC while within range of the selected objective marker
            # and the bearer is on the battlefield.
            try:
                army = self.get_parent_army()
            except Exception:
                army = None
            try:
                tau_mgr = getattr(army, "tau_empire_detachments", None) if army is not None else None
                if tau_mgr is not None:
                    bonus = int(
                        tau_mgr.strategic_conqueror_objective_control_bonus(
                            model,
                            game_map=game_map,
                        )
                        or 0
                    )
                    if bonus:
                        mods.append(Modifier(ModifierOp.ADD, int(bonus), source="enhancement:strategic_conqueror"))
            except Exception:
                pass

            # Kill-reward persistent Objective Control bonuses (e.g. Trophy Takers).
            try:
                sr_root = getattr(root, "special_rules", None)
                entries = sr_root.get("kill_reward_objective_control_bonus_entries") if isinstance(sr_root, dict) else None
                if isinstance(entries, list):
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        try:
                            bonus = int(entry.get("bonus", 0) or 0)
                        except Exception:
                            continue
                        if bonus <= 0:
                            continue
                        try:
                            stacks = int(entry.get("stacks", 1) or 1)
                        except Exception:
                            stacks = 1
                        stacks = max(1, int(stacks))
                        if bool(entry.get("requires_not_battle_shocked", False)) and root.is_battle_shocked():
                            continue
                        source = str(entry.get("source", "") or "Kill reward").strip() or "Kill reward"
                        mods.append(
                            Modifier(
                                ModifierOp.ADD,
                                int(bonus * stacks),
                                source=f"ability:kill_reward_objective_control:{source}",
                            )
                        )
            except Exception:
                pass

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

            # Friendly OC auras (ADD) – applied as an ADD modifier so DIV happens first.
            try:
                from ..utility.aura_effects import get_aura_objective_control_bonus
                bonus = int(get_aura_objective_control_bonus(self, game_map=game_map) or 0)
                if bonus:
                    mods.append(Modifier(ModifierOp.ADD, bonus, source="aura:objective_control_add"))
            except Exception:
                pass
            try:
                from ..utility.aura_effects import (
                    get_enemy_aura_move_oc_penalties,
                    get_enemy_aura_objective_control_minimum_floor,
                )
                _move_pen, oc_pen = get_enemy_aura_move_oc_penalties(self, game_map=game_map)
                if oc_pen:
                    mods.append(Modifier(ModifierOp.ADD, int(oc_pen), source="aura:enemy_objective_control_penalty"))
                aura_oc_floor = get_enemy_aura_objective_control_minimum_floor(self, game_map=game_map)
                if int(aura_oc_floor or 0) > 0:
                    objective_control_floor = max(objective_control_floor, int(aura_oc_floor))
            except Exception:
                pass

            # Pledge of Dark Glory: while the bearer is leading a unit, improve
            # Objective Control characteristics of models in that unit by 1.
            try:
                if _enhancement_bearer_is_leading("enhancement_pledge_of_dark_glory"):
                    mods.append(Modifier(ModifierOp.ADD, 1, source="enhancement:pledge_of_dark_glory"))
            except Exception:
                pass

            # Proud and Vainglorious (Slaanesh's Chosen): while the bearer's unit is
            # Favoured Champions, add to Objective Control.
            try:
                root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
            except Exception:
                root = self
            try:
                army = root.get_parent_army() if root is not None else None
            except Exception:
                army = None
            try:
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is None and army is not None:
                    mgr = getattr(army, "emperors_children_detachments", None)
            except Exception:
                mgr = None
            if mgr is not None and bool(getattr(mgr, "is_favoured_champions", lambda _u: False)(root)):
                has_proud = False
                try:
                    checker = getattr(root, "_attached_unit_has_active_enhancement", None)
                    if callable(checker):
                        has_proud = bool(
                            checker(
                                "enhancement_proud_and_vainglorious",
                                enhancement_id="000010018004",
                                enhancement_name="proud and vainglorious",
                            )
                        )
                except Exception:
                    has_proud = False
                if has_proud:
                    bonus = 0
                    try:
                        members = list(root.get_attached_unit_members() or [])
                    except Exception:
                        members = [root]
                    if not members:
                        members = [root]
                    for member in members:
                        sr_member = getattr(member, "special_rules", None)
                        if not isinstance(sr_member, dict):
                            continue
                        if not sr_member.get("enhancement_proud_and_vainglorious"):
                            continue
                        try:
                            bonus = max(
                                bonus,
                                int(sr_member.get("enhancement_proud_and_vainglorious_oc_bonus", 1) or 1),
                            )
                        except Exception:
                            continue
                    if bonus:
                        mods.append(
                            Modifier(
                                ModifierOp.ADD,
                                int(bonus),
                                source="enhancement:proud_and_vainglorious_favoured",
                            )
                        )

        if ckey == "toughness":
            if game_map is None:
                try:
                    army = self.get_parent_army()
                    game = getattr(getattr(army, "player", None), "game", None)
                    game_map = getattr(game, "map", None) if game is not None else None
                except Exception:
                    game_map = None
            try:
                from ..utility.aura_effects import get_aura_toughness_bonus
                bonus, _reasons = get_aura_toughness_bonus(self, game_map=game_map)
                if bonus:
                    mods.append(Modifier(ModifierOp.ADD, int(bonus), source="aura:toughness_add"))
            except Exception:
                pass
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict):
                    bonus = int(sr.get("daemonic_allegiance_toughness_bonus", 0) or 0)
                    if bonus:
                        mods.append(Modifier(ModifierOp.ADD, int(bonus), source="daemonic_allegiance:toughness_add"))
            except Exception:
                pass
            try:
                bonus_fn = getattr(self, "get_enhanced_warriors_toughness_bonus", None)
                if callable(bonus_fn):
                    ew_bonus, ew_source = bonus_fn(model)
                    if int(ew_bonus or 0):
                        source = str(ew_source or "Enhanced Warriors").strip() or "Enhanced Warriors"
                        mods.append(
                            Modifier(
                                ModifierOp.ADD,
                                int(ew_bonus),
                                source=f"ability:enhanced_warriors_toughness:{source}",
                            )
                        )
            except Exception:
                pass
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict) and sr.get("nurgles_rot_active"):
                    penalty = int(sr.get("nurgles_rot_penalty", 0) or 0)
                    if penalty:
                        source = str(sr.get("nurgles_rot_source", "") or "Nurgle's Rot").strip() or "Nurgle's Rot"
                        mods.append(Modifier(ModifierOp.ADD, int(penalty), source=f"ability:nurgles_rot:{source}"))
            except Exception:
                pass

        if ckey == "leadership":
            if game_map is None:
                try:
                    army = self.get_parent_army()
                    game = getattr(getattr(army, "player", None), "game", None)
                    game_map = getattr(game, "map", None) if game is not None else None
                except Exception:
                    game_map = None
            if game_map is not None:
                from ..utility.aura_utils import unit_within_range_of_unit
                get_enemy_units = getattr(game_map, "get_enemy_units", None)
                if callable(get_enemy_units):
                    for enemy in list(get_enemy_units(self) or []):
                        blue_active_fn = getattr(enemy, "_horrors_blue_abilities_active", None)
                        if not callable(blue_active_fn) or not blue_active_fn():
                            continue
                        blue_models_fn = getattr(enemy, "_horrors_has_blue_models", None)
                        if not callable(blue_models_fn) or not blue_models_fn():
                            continue
                            if unit_within_range_of_unit(enemy, self, 6.0):
                                mods.append(Modifier(ModifierOp.ADD, 1, source="aura:sullen_malevolence"))
                                break
                try:
                    from ..utility.aura_effects import get_aura_leadership_bonus
                    bonus = int(get_aura_leadership_bonus(self, game_map=game_map) or 0)
                    if bonus:
                        mods.append(Modifier(ModifierOp.ADD, bonus, source="aura:leadership_add"))
                except Exception:
                    pass
                try:
                    from ..utility.aura_effects import get_enemy_aura_leadership_characteristic_penalty
                    penalty = int(get_enemy_aura_leadership_characteristic_penalty(self, game_map=game_map) or 0)
                    if penalty:
                        mods.append(Modifier(ModifierOp.ADD, int(penalty), source="aura:enemy_leadership_penalty"))
                except Exception:
                    pass
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict):
                    entries = list(sr.get("bearer_unit_leadership_bonus_controlled_objective", []) or [])
                else:
                    entries = []
                if entries and self._within_controlled_objective_range(game_map=game_map):
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        try:
                            val = int(entry.get("value", 0) or 0)
                        except Exception:
                            continue
                        if not val:
                            continue
                        source = str(entry.get("source", "") or "Bearer unit ability").strip() or "Bearer unit ability"
                        mods.append(
                            Modifier(
                                ModifierOp.ADD,
                                int(val),
                                source=f"ability:bearer_unit_leadership_objective:{source}",
                            )
                        )
            except Exception:
                pass
            try:
                if _enhancement_bearer_is_leading("enhancement_pledge_of_dark_glory"):
                    # Leadership is better at lower values, so +1 improvement is a -1 modifier.
                    mods.append(Modifier(ModifierOp.ADD, -1, source="enhancement:pledge_of_dark_glory"))
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

        if afflicted_plague is not None:
            if ckey == "save" and afflicted_plague.key == PLAGUE_RATTLEJOINT.key:
                mods.append(Modifier(ModifierOp.ADD, 1, source="nurgles_gift:rattlejoint_ague"))
            elif ckey == "movement" and afflicted_plague.key == PLAGUE_SCABROUS.key:
                mods.append(Modifier(ModifierOp.ADD, -1, source="nurgles_gift:scabrous_soulrot"))
            elif ckey == "leadership" and afflicted_plague.key == PLAGUE_SCABROUS.key:
                mods.append(Modifier(ModifierOp.ADD, 1, source="nurgles_gift:scabrous_soulrot"))
            elif ckey == "objective_control" and afflicted_plague.key == PLAGUE_SCABROUS.key:
                mods.append(Modifier(ModifierOp.ADD, -1, source="nurgles_gift:scabrous_soulrot"))
                objective_control_floor = max(objective_control_floor, 1)

        try:
            army = self.get_parent_army()
            mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
            if mgr is not None:
                game = getattr(getattr(army, "player", None), "game", None)
                keys = mgr.get_active_combat_drug_keys_for_model(model, game=game)
                if keys:
                    if ckey == "movement" and "HYPEX" in keys:
                        mods.append(Modifier(ModifierOp.ADD, 2, source="combat_drugs:hypex_move"))
                    if ckey == "toughness" and "PAINBRINGER" in keys:
                        mods.append(Modifier(ModifierOp.ADD, 1, source="combat_drugs:painbringer_toughness"))
                    if ckey == "leadership" and "SPLINTERMIND" in keys:
                        mods.append(Modifier(ModifierOp.ADD, -1, source="combat_drugs:splintermind_leadership"))
        except Exception:
            pass

        if ckey == "movement":
            if game_map is None:
                try:
                    army = self.get_parent_army()
                    game = getattr(getattr(army, "player", None), "game", None)
                    game_map = getattr(game, "map", None) if game is not None else None
                except Exception:
                    game_map = None
            army = self.get_parent_army()
            mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            applies_fn = getattr(mgr, "idols_of_khorne_burning_wrath_applies", None) if mgr is not None else None
            if callable(applies_fn) and applies_fn(self, game_map=game_map):
                mods.append(Modifier(ModifierOp.ADD, 1, source="idols_of_khorne:burning_wrath"))
            try:
                bonus = int(getattr(model, "get_temporary_movement_bonus", lambda: 0)() or 0)
            except Exception:
                bonus = 0
            if bonus:
                mods.append(Modifier(ModifierOp.ADD, int(bonus), source="ability:temporary_movement_add"))
            try:
                from ..rules.thousand_sons_crimson_king import time_flux_move_bonus_for_unit
                bonus = int(time_flux_move_bonus_for_unit(self, game_map=game_map) or 0)
                if bonus:
                    mods.append(Modifier(ModifierOp.ADD, int(bonus), source="ability:time_flux"))
            except Exception:
                pass
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict):
                    daemonic_bonus = int(sr.get("daemonic_allegiance_move_bonus", 0) or 0)
                    if daemonic_bonus:
                        mods.append(Modifier(ModifierOp.ADD, int(daemonic_bonus), source="daemonic_allegiance:move_add"))
            except Exception:
                pass
                try:
                    from ..utility.aura_effects import get_enemy_aura_move_oc_penalties
                    move_pen, _oc_pen = get_enemy_aura_move_oc_penalties(self, game_map=game_map)
                    if move_pen:
                        mods.append(Modifier(ModifierOp.ADD, int(move_pen), source="aura:enemy_move_penalty"))
                except Exception:
                    pass
            try:
                sr = getattr(self, "special_rules", None)
                if isinstance(sr, dict) and sr.get("flickerjump_move_set_value"):
                    move_value = int(sr.get("flickerjump_move_set_value", 0) or 0)
                    owner = str(sr.get("flickerjump_move_set_turn_owner", "") or "")
                    turn = int(sr.get("flickerjump_move_set_turn", 0) or 0)
                    game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    if (
                        move_value > 0
                        and owner
                        and game is not None
                        and str(getattr(game.get_current_player(), "id", "") or "") == owner
                        and int(getattr(game, "turn", 0) or 0) == turn
                    ):
                        mods.append(Modifier(ModifierOp.SET, int(move_value), source="ability:flickerjump_move_set"))
            except Exception:
                pass

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
            from ..rules.psychic_guidance import psychic_guidance_leadership_value
            pg_value = psychic_guidance_leadership_value(model)
            if pg_value is not None:
                mods.append(Modifier(ModifierOp.SET, int(pg_value), source="ability:psychic_guidance"))

        return mods, int(max(0, objective_control_floor)), game_map

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

        mods, objective_control_floor, game_map = Unit._collect_characteristic_modifiers(
            self,
            model,
            ckey,
            base_val=base_val,
            base_raw=base_raw,
            game_map=game_map,
        )

        # Emperor's Children: Internal Rivalries (Slaanesh's Chosen) - optional ignore Move modifiers.
        try:
            if ckey == "movement":
                army = self.get_parent_army()
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is None and army is not None:
                    mgr = getattr(army, "emperors_children_detachments", None)
                if mgr is not None and getattr(mgr, "internal_rivalries_applies", lambda _u: False)(self):
                    from ..utility.modifier_choice import (
                        CHOICE_KEEP_ALL,
                        CHOICE_IGNORE_NEGATIVE,
                        CHOICE_IGNORE_POSITIVE,
                        CHOICE_IGNORE_ALL,
                        filter_numeric_modifiers,
                    )
                    try:
                        choice = str(getattr(self.round_state, "move_modifier_choice", "") or "").strip()
                    except Exception:
                        choice = ""
                    if not choice:
                        choice = CHOICE_KEEP_ALL
                    if choice != CHOICE_KEEP_ALL:
                        kept, ignored = filter_numeric_modifiers(mods, choice, base_val=base_val)
                        if ignored:
                            mods = kept
                            try:
                                sr = getattr(self, "special_rules", None)
                                if not isinstance(sr, dict):
                                    sr = {}
                                ignored_sources = tuple(sorted(str(getattr(m, "source", "") or "") for m in ignored))
                                kept_sources = tuple(sorted(str(getattr(m, "source", "") or "") for m in kept))
                                sig = (ignored_sources, kept_sources, choice)
                                if sr.get("internal_rivalries_move_mod_signature") != sig:
                                    sr["internal_rivalries_move_mod_signature"] = sig
                                    self.special_rules = sr
                                    from ..utility.event_bus import append_action
                                    pn = self.get_parent_army().player
                                    ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                                    tag = (
                                        "negative"
                                        if choice == CHOICE_IGNORE_NEGATIVE
                                        else "positive"
                                        if choice == CHOICE_IGNORE_POSITIVE
                                        else "all"
                                    )
                                    msg = f"Internal Rivalries: ignored {tag} Move modifiers ({ignored_text})."
                                    append_action(pn, msg)
                                    if kept_sources:
                                        kept_text = ", ".join(s for s in kept_sources if s)
                                        if kept_text:
                                            append_action(pn, f"Internal Rivalries: applied Move modifiers ({kept_text}).")
                            except Exception:
                                pass
        except Exception:
            pass

        # World Eaters: Driven by Ultimate Rage (Aura) - optional ignore Move modifiers.
        try:
            if ckey == "movement":
                from ..rules.wrathful_presence import driven_by_ultimate_rage_applies
                if driven_by_ultimate_rage_applies(self, game_map=game_map):
                    from ..utility.modifier_choice import (
                        CHOICE_KEEP_ALL,
                        CHOICE_IGNORE_NEGATIVE,
                        CHOICE_IGNORE_POSITIVE,
                        CHOICE_IGNORE_ALL,
                        filter_numeric_modifiers,
                    )
                    try:
                        choice = str(getattr(self.round_state, "move_modifier_choice", "") or "").strip()
                    except Exception:
                        choice = ""
                    if not choice:
                        choice = CHOICE_KEEP_ALL
                    if choice != CHOICE_KEEP_ALL:
                        kept, ignored = filter_numeric_modifiers(mods, choice, base_val=base_val)
                        if ignored:
                            mods = kept
                            try:
                                sr = getattr(self, "special_rules", None)
                                if not isinstance(sr, dict):
                                    sr = {}
                                ignored_sources = tuple(sorted(str(getattr(m, "source", "") or "") for m in ignored))
                                kept_sources = tuple(sorted(str(getattr(m, "source", "") or "") for m in kept))
                                sig = (ignored_sources, kept_sources, choice)
                                if sr.get("driven_by_ultimate_rage_move_mod_signature") != sig:
                                    sr["driven_by_ultimate_rage_move_mod_signature"] = sig
                                    self.special_rules = sr
                                    from ..utility.event_bus import append_action
                                    pn = self.get_parent_army().player
                                    ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                                    tag = (
                                        "negative"
                                        if choice == CHOICE_IGNORE_NEGATIVE
                                        else "positive"
                                        if choice == CHOICE_IGNORE_POSITIVE
                                        else "all"
                                    )
                                    msg = f"Driven by Ultimate Rage: ignored {tag} Move modifiers ({ignored_text})."
                                    append_action(pn, msg)
                                    if kept_sources:
                                        kept_text = ", ".join(s for s in kept_sources if s)
                                        if kept_text:
                                            append_action(pn, f"Driven by Ultimate Rage: applied Move modifiers ({kept_text}).")
                            except Exception:
                                pass
        except Exception:
            pass

        # Chaos Knights: Bestial Aspect (while Unholy Hunger) - optional ignore Move modifiers.
        try:
            if ckey == "movement" and self._bestial_aspect_unholy_hunger_active(game_map=game_map):
                from ..utility.modifier_choice import (
                    CHOICE_KEEP_ALL,
                    CHOICE_IGNORE_NEGATIVE,
                    CHOICE_IGNORE_POSITIVE,
                    CHOICE_IGNORE_ALL,
                    filter_numeric_modifiers,
                )
                try:
                    choice = str(getattr(self.round_state, "move_modifier_choice", "") or "").strip()
                except Exception:
                    choice = ""
                if not choice:
                    choice = CHOICE_KEEP_ALL
                if choice != CHOICE_KEEP_ALL:
                    kept, ignored = filter_numeric_modifiers(mods, choice, base_val=base_val)
                    if ignored:
                        mods = kept
                        try:
                            sr = getattr(self, "special_rules", None)
                            if not isinstance(sr, dict):
                                sr = {}
                            ignored_sources = tuple(sorted(str(getattr(m, "source", "") or "") for m in ignored))
                            kept_sources = tuple(sorted(str(getattr(m, "source", "") or "") for m in kept))
                            sig = (ignored_sources, kept_sources, choice)
                            if sr.get("bestial_aspect_move_mod_signature") != sig:
                                sr["bestial_aspect_move_mod_signature"] = sig
                                self.special_rules = sr
                                from ..utility.event_bus import append_action
                                pn = self.get_parent_army().player
                                ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                                tag = (
                                    "negative"
                                    if choice == CHOICE_IGNORE_NEGATIVE
                                    else "positive"
                                    if choice == CHOICE_IGNORE_POSITIVE
                                    else "all"
                                )
                                msg = f"Bestial Aspect: ignored {tag} Move modifiers ({ignored_text})."
                                append_action(pn, msg)
                                if kept_sources:
                                    kept_text = ", ".join(s for s in kept_sources if s)
                                    if kept_text:
                                        append_action(pn, f"Bestial Aspect: applied Move modifiers ({kept_text}).")
                        except Exception:
                            pass
        except Exception:
            pass

        # Drukhari: Preternatural Agility - optional ignore Move modifiers this phase.
        try:
            if ckey == "movement":
                active_fn = getattr(self, "_preternatural_agility_ignore_modifiers_active", None)
                if callable(active_fn) and bool(active_fn()):
                    from ..utility.modifier_choice import (
                        CHOICE_KEEP_ALL,
                        CHOICE_IGNORE_NEGATIVE,
                        CHOICE_IGNORE_POSITIVE,
                        CHOICE_IGNORE_ALL,
                        filter_numeric_modifiers,
                    )
                    try:
                        choice = str(getattr(self.round_state, "move_modifier_choice", "") or "").strip()
                    except Exception:
                        choice = ""
                    if not choice:
                        choice = CHOICE_KEEP_ALL
                    if choice != CHOICE_KEEP_ALL:
                        kept, ignored = filter_numeric_modifiers(mods, choice, base_val=base_val)
                        if ignored:
                            mods = kept
                            try:
                                sr = getattr(self, "special_rules", None)
                                if not isinstance(sr, dict):
                                    sr = {}
                                ignored_sources = tuple(sorted(str(getattr(m, "source", "") or "") for m in ignored))
                                kept_sources = tuple(sorted(str(getattr(m, "source", "") or "") for m in kept))
                                sig = (ignored_sources, kept_sources, choice)
                                if sr.get("preternatural_agility_move_mod_signature") != sig:
                                    sr["preternatural_agility_move_mod_signature"] = sig
                                    self.special_rules = sr
                                    from ..utility.event_bus import append_action
                                    pn = self.get_parent_army().player
                                    ignored_text = ", ".join(s for s in ignored_sources if s) or "unnamed sources"
                                    tag = (
                                        "negative"
                                        if choice == CHOICE_IGNORE_NEGATIVE
                                        else "positive"
                                        if choice == CHOICE_IGNORE_POSITIVE
                                        else "all"
                                    )
                                    msg = f"Preternatural Agility: ignored {tag} Move modifiers ({ignored_text})."
                                    append_action(pn, msg)
                                    if kept_sources:
                                        kept_text = ", ".join(s for s in kept_sources if s)
                                        if kept_text:
                                            append_action(pn, f"Preternatural Agility: applied Move modifiers ({kept_text}).")
                            except Exception:
                                pass
        except Exception:
            pass

        # Siege Crawler: ignore all Move characteristic modifiers.
        if ckey == "movement" and bool(getattr(self, "has_siege_crawler", lambda: False)()):
            mods = []

        # Apply core ordering + rounding.
        interim, dbg = apply_numeric_modifiers(int(base_val), mods, base_raw=base_raw)

        # Damage 0 exception handled at weapon level, not model level.
        final = apply_characteristic_caps(ckey, interim, base_raw=base_raw)
        if ckey == "objective_control" and int(base_val) > 0 and int(objective_control_floor or 0) > 0:
            final = max(int(final), int(objective_control_floor))
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
        try:
            if "defensive_ap_worsen" in self.special_rules:
                del self.special_rules["defensive_ap_worsen"]
        except Exception:
            pass
        try:
            entries = self.special_rules.get("defensive_wound_mods")
            if isinstance(entries, list):
                kept = [
                    e
                    for e in entries
                    if not isinstance(e, dict)
                    or e.get("tag") not in (
                        "ability:strength_gt_toughness_wound_penalty",
                        "ability:defensive_wound_penalty",
                    )
                ]
                if kept:
                    self.special_rules["defensive_wound_mods"] = kept
                elif "defensive_wound_mods" in self.special_rules:
                    del self.special_rules["defensive_wound_mods"]
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
        for ab, _leader in self._iter_attached_leader_leading_abilities():
            try:
                if isinstance(ab, str):
                    name = str(ab or "")
                    desc = str(ab or "")
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            entries.append((name, desc or name))

        def _normalize_leading_keyword(raw_kw: str) -> str:
            kw = str(raw_kw or "").strip()
            if not kw:
                return ""
            kw = self._normalize_keyword_phrase(kw) or kw.upper()
            kw = re.sub(r"\bmodels?\b$", "", kw).strip()
            return kw

        for name, raw in entries:
            t = self._normalize_rules_text(raw)
            if not t:
                continue
            tl = t.lower()
            sentences = [part.strip() for part in re.split(r"[.;]\s*", raw or "") if part.strip()]

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

            # Generic wound roll penalty when attacks target this unit/model.
            seen_generic_wound_mods = set()
            for sentence in sentences:
                if not sentence:
                    continue
                norm = self._normalize_rules_text(sentence)
                if not norm:
                    continue
                norm = norm.replace("\u2019", "'").replace("\u0192?T", "'")
                norm = norm.lower()
                norm = re.sub(r"'s\b", "s", norm)
                norm = re.sub(r"[^a-z0-9]+", " ", norm)
                norm = re.sub(r"\s+", " ", norm).strip()
                if "strength characteristic" in norm:
                    continue
                pattern = (
                    r"(?:while (?:(?:a|an|the) (?P<lemma>[a-z0-9 ]+)|this)(?: model)? is leading (?:this|a) unit |"
                    r"while this unit contains one or more (?P<lemma_contains>[a-z0-9 ]+) models )?"
                    r"each time (?:an|a) (?:(?P<atype>melee|ranged) )?attack(?:s)? "
                    r"(?:targets|target|is allocated to) "
                    r"(?:this model|this unit|this model s unit|a model in this unit) "
                    r"subtract (?P<val>\d+) from (?:the|that|that attacks) wound roll(?:s)?"
                )
                m = re.fullmatch(pattern, norm)
                if not m:
                    continue
                try:
                    val = int(m.group("val"))
                except Exception:
                    val = 0
                if not val:
                    continue
                atype = (m.group("atype") or "any").strip().lower()
                leader_kw = _normalize_leading_keyword(m.group("lemma"))
                contains_kw = _normalize_leading_keyword(m.group("lemma_contains"))
                label = (name or "Defensive ability").strip() or "Defensive ability"
                key = (label.lower(), atype, int(val), leader_kw or "", contains_kw or "")
                if key in seen_generic_wound_mods:
                    continue
                seen_generic_wound_mods.add(key)
                sr = self.special_rules
                items = list(sr.get("defensive_wound_mods", []) or [])
                entry = {
                    "value": int(val),
                    "attack_type": atype,
                    "source": label,
                    "tag": "ability:defensive_wound_penalty",
                }
                if leader_kw:
                    entry["requires_leading_keyword"] = str(leader_kw)
                if contains_kw:
                    entry["requires_unit_contains_keyword"] = str(contains_kw)
                items.append(entry)
                sr["defensive_wound_mods"] = items
                self.special_rules = sr

            # Wound roll penalty when incoming attack Strength exceeds target Toughness.
            seen_wound_mods = set()
            for sentence in sentences:
                if not sentence:
                    continue
                norm = self._normalize_rules_text(sentence)
                if not norm:
                    continue
                norm = norm.replace("\u2019", "'").replace("\u0192?T", "'")
                norm = norm.lower()
                norm = re.sub(r"'s\b", "s", norm)
                norm = re.sub(r"[^a-z0-9]+", " ", norm)
                norm = re.sub(r"\s+", " ", norm).strip()
                pattern = (
                    r"(?:while (?:(?:a|an|the) (?P<lemma>[a-z0-9 ]+)|this)(?: model)? is leading (?:this|a) unit )?"
                    r"each time (?:an|a) (?:(?P<atype>melee|ranged) )?attack(?:s)? "
                    r"(?:targets|target|is allocated to) "
                    r"(?:this model|this unit|this model s unit|a model in this unit) "
                    r"if (?:the )?(?:strength characteristic of that attack|that attacks strength characteristic) "
                    r"is greater than "
                    r"(?:the toughness characteristic of (?:this model|this unit|that model)|(?:this model|this unit|that model)s toughness characteristic) "
                    r"subtract (?P<val>\d+) from (?:the|that|that attacks) wound roll(?:s)?"
                )
                m = re.fullmatch(pattern, norm)
                if not m:
                    continue
                try:
                    val = int(m.group("val"))
                except Exception:
                    val = 0
                if not val:
                    continue
                atype = (m.group("atype") or "any").strip().lower()
                leader_kw = _normalize_leading_keyword(m.group("lemma"))
                label = (name or "Defensive ability").strip() or "Defensive ability"
                key = (label.lower(), atype, int(val), leader_kw or "")
                if key in seen_wound_mods:
                    continue
                seen_wound_mods.add(key)
                sr = self.special_rules
                items = list(sr.get("defensive_wound_mods", []) or [])
                entry = {
                    "value": int(val),
                    "attack_type": atype,
                    "source": label,
                    "requires_strength_gt_toughness": True,
                    "tag": "ability:strength_gt_toughness_wound_penalty",
                }
                if leader_kw:
                    entry["requires_leading_keyword"] = str(leader_kw)
                items.append(entry)
                sr["defensive_wound_mods"] = items
                self.special_rules = sr

            # AP worsen when attacks target this unit/model.
            seen_ap_worsen = set()
            for sentence in sentences:
                if not sentence:
                    continue
                norm = self._normalize_rules_text(sentence)
                if not norm:
                    continue
                norm = norm.replace("\u2019", "'").replace("\u0192?T", "'")
                norm = norm.lower()
                norm = re.sub(r"'s\b", "s", norm)
                norm = re.sub(r"[^a-z0-9]+", " ", norm)
                norm = re.sub(r"\s+", " ", norm).strip()
                pattern = (
                    r"(?:while (?:(?:a|an|the) (?P<lemma>[a-z0-9 ]+)|this)(?: model)? is leading (?:this|a) unit )?"
                    r"each time (?:an|a) (?:(?P<atype>melee|ranged) )?attack(?:s)? "
                    r"(?:targets|target) "
                    r"(?:this model|this unit|this model s unit|that unit|the bearer s unit) "
                    r"worsen the armou?r penetration characteristic of that attack by (?P<val>\d+)"
                )
                m = re.fullmatch(pattern, norm)
                if not m:
                    continue
                try:
                    val = int(m.group("val"))
                except Exception:
                    val = 0
                if not val:
                    continue
                atype = (m.group("atype") or "any").strip().lower()
                leader_kw = _normalize_leading_keyword(m.group("lemma"))
                label = (name or "Defensive ability").strip() or "Defensive ability"
                key = (label.lower(), atype, int(val), leader_kw or "")
                if key in seen_ap_worsen:
                    continue
                seen_ap_worsen.add(key)
                sr = self.special_rules
                items = list(sr.get("defensive_ap_worsen", []) or [])
                entry = {
                    "value": int(val),
                    "attack_type": atype,
                    "source": label,
                    "tag": "ability:defensive_ap_worsen",
                }
                if leader_kw:
                    entry["requires_leading_keyword"] = str(leader_kw)
                items.append(entry)
                sr["defensive_ap_worsen"] = items
                self.special_rules = sr

    def _matches_enemy_melee_hazardous_while_targeted(self, text: str) -> bool:
        if not text:
            return False
        normalized = self._normalize_rules_text(text)
        if not normalized:
            return False
        normalized = normalized.replace("\u2019", "'").lower().strip()
        normalized = re.sub(r"'s\b", "s", normalized)
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return bool(self._ENEMY_MELEE_HAZARDOUS_WHILE_TARGETING_RE.search(normalized))

    def enemy_melee_weapons_hazardous_while_targeted(self) -> list[str]:
        """
        Return source names for abilities that make enemy melee weapons Hazardous while targeting this unit.
        """
        root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
        cache_key = "enemy_melee_hazardous_while_targeted"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return cache[cache_key]

        sources: list[str] = []
        members = root.get_attached_unit_members() if hasattr(root, "get_attached_unit_members") else [root]
        for unit in members:
            for ab in unit._iter_active_possible_abilities():
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "")
                text = desc or name
                if text and self._matches_enemy_melee_hazardous_while_targeted(text):
                    sources.append(name or "Ability")
            for model in list(getattr(unit, "models", []) or []):
                abilities = getattr(model, "abilities", {}) or {}
                for ab in abilities.values():
                    if isinstance(ab, str):
                        name = ab
                        desc = ab
                    else:
                        name = str(getattr(ab, "name", "") or "")
                        desc = str(getattr(ab, "description", "") or "")
                    text = desc or name
                    if text and self._matches_enemy_melee_hazardous_while_targeted(text):
                        sources.append(name or "Ability")

        # De-dup while preserving order
        deduped: list[str] = []
        seen: set[str] = set()
        for src in sources:
            key = str(src or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(key)

        if not isinstance(cache, dict):
            root._ability_cache = {}
            cache = root._ability_cache
        cache[cache_key] = deduped
        return deduped

    _CANNOT_BE_WARLORD_RE = re.compile(
        r"\bcannot be(?: selected as)? your\s+warlord\b",
        re.IGNORECASE,
    )
    _CANNOT_BE_GIVEN_ENHANCEMENTS_RE = re.compile(r"\bcannot be given\s+(?:an?\s+)?enhancements?\b", re.IGNORECASE)
    _BEARER_UNIT_CHARGE_BONUS_RE = re.compile(
        r"add\s+(\d+)\s+to\s+charge\s+rolls?\s+made\s+for\s+(?:the\s+bearer'?s\s+unit|this\s+unit|this\s+model'?s\s+unit)",
        re.IGNORECASE,
    )
    _BEARER_UNIT_ADVANCE_BONUS_RE = re.compile(
        r"add\s+(\d+)\s+to\s+advance\s+rolls?\s+made\s+for\s+(?:the\s+bearer'?s\s+unit|this\s+unit|this\s+model'?s\s+unit)",
        re.IGNORECASE,
    )
    _BEARER_UNIT_ADVANCE_AND_CHARGE_BONUS_RE = re.compile(
        r"add\s+(\d+)\s+to\s+advance\s+and\s+charge\s+rolls?\s+made\s+for\s+(?:the\s+bearer'?s\s+unit|this\s+unit|this\s+model'?s\s+unit)",
        re.IGNORECASE,
    )
    _ADVANCE_NO_ROLL_MOVE_RE = re.compile(
        r"do\s+not\s+make\s+an?\s+advance\s+roll.*?add\s+(\d+)\s*(?:\"|inches)?\s+to\s+the\s+move\s+characteristic",
        re.IGNORECASE,
    )
    _ADVANCE_IGNORE_VERTICAL_RE = re.compile(
        r"ignore\s+(?:any\s+)?vertical\s+distance",
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
    _BEARER_UNIT_CONTROLLED_OBJECTIVE_LEADERSHIP_IMPROVE_RE = re.compile(
        r"while\s+the\s+bearer'?s\s+unit\s+is\s+within\s+range\s+of\s+(?:an|one\s+or\s+more)\s+objective\s+markers?\s+you\s+control,?\s*"
        r"improve\s+the\s+leadership\s+characteristic\s+of\s+models\s+in\s+the\s+bearer'?s\s+unit\s+by\s+(\d+)",
        re.IGNORECASE,
    )
    _BEARER_UNIT_MOVEMENT_SET_RE = re.compile(
        r"models\s+in\s+the\s+bearer'?s\s+unit\s+have\s+a\s+move\s+characteristic\s+of\s+(\d+)",
        re.IGNORECASE,
    )
    _BEARER_UNIT_MOVEMENT_BONUS_RE = re.compile(
        r"add\s+(\d+)\s*(?:\"|inches)?\s+to\s+the\s+move\s+characteristic\s+of\s+"
        r"(?:models\s+in\s+)?(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit|this\s+model'?s\s+unit)",
        re.IGNORECASE,
    )
    _BEARER_UNIT_OC_BONUS_RE = re.compile(
        r"add\s+(\d+)\s+to\s+the\s+objective\s+control\s+characteristic\s+of\s+(?:models\s+in\s+)?the\s+bearer'?s\s+unit",
        re.IGNORECASE,
    )
    _BEARER_UNIT_PILE_IN_CONSOLIDATE_DISTANCE_OVERRIDE_RE = re.compile(
        r"each\s+time\s+(?:this\s+unit|the\s+bearer'?s\s+unit|this\s+model'?s\s+unit|that\s+unit)\s+"
        r"(?:(?:piles?\s+in)|(?:makes\s+a\s+pile[-\s]?in\s+move))\s+or\s+"
        r"(?:consolidates|makes\s+a\s+consolidation\s+move)\s*,?\s*"
        r"(?:it|models\s+in\s+(?:it|that\s+unit|the\s+bearer'?s\s+unit)|each\s+model\s+in\s+(?:it|that\s+unit|the\s+bearer'?s\s+unit))\s+can\s+move\s+"
        r"up\s+to\s+(\d+)\s*(?:\"|inches)?\s+instead\s+of\s+up\s+to\s+3\s*(?:\"|inches)?",
        re.IGNORECASE,
    )
    _BEARER_UNIT_CONSOLIDATE_DISTANCE_OVERRIDE_RE = re.compile(
        r"each\s+time\s+(?:this\s+unit|the\s+bearer'?s\s+unit|this\s+model'?s\s+unit|that\s+unit)\s+"
        r"(?:consolidates|makes\s+a\s+consolidation\s+move)\s*,?\s*"
        r"(?:it|models\s+in\s+(?:it|that\s+unit|the\s+bearer'?s\s+unit)|each\s+model\s+in\s+(?:it|that\s+unit|the\s+bearer'?s\s+unit))\s+can\s+move\s+"
        r"up\s+to\s+(\d+)\s*(?:\"|inches)?\s+instead\s+of\s+up\s+to\s+3\s*(?:\"|inches)?\s*$",
        re.IGNORECASE,
    )
    _BEARER_UNIT_CONSOLIDATE_ADDITIONAL_DISTANCE_IF_ENGAGEMENT_RE = re.compile(
        r"each\s+time\s+(?:this\s+unit|the\s+bearer'?s\s+unit|this\s+model'?s\s+unit|that\s+unit|your\s+unit)\s+"
        r"(?:consolidates|makes\s+a\s+consolidation\s+move)\s*,?\s*"
        r"(?:it|models\s+in\s+(?:it|that\s+unit|the\s+bearer'?s\s+unit|your\s+unit)|each\s+model\s+in\s+(?:it|that\s+unit|the\s+bearer'?s\s+unit|your\s+unit))\s+can\s+move\s+"
        r"an?\s+additional\s+(\d+)\s*(?:\"|inches)?\s+"
        r"(?:provided|as\s+long\s+as)\s+(?:your\s+unit|that\s+unit|this\s+unit)\s+"
        r"(?:can\s+end|ends)\s+that\s+(?:consolidation\s+)?move\s+within\s+engagement\s+range\s+of\s+one\s+or\s+more\s+enemy\s+units?\s*$",
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
    _BEARER_UNIT_KEYWORD_FNP_RE = re.compile(
        r"if\s+(?:the\s+)?(?:bearer'?s|that|this)\s+unit\s+has\s+(?:the\s+)?(?P<keyword>[a-z0-9][a-z0-9 '\-]*)\s+keyword,?\s*"
        r"(?:models?\s+in\s+)?(?:the\s+bearer'?s|that|this)\s+unit\s+have\s+(?:a|the)?\s*feel\s+no\s+pain\s*(?P<value>[1-6])\+?(?:\s+ability)?(?:\s+instead)?",
        re.IGNORECASE,
    )
    _ATTACHED_CHARACTER_FNP_RE = re.compile(
        r"(?:other\s+character\s+models\s+attached\s+to\s+(?:that\s+unit|the\s+bearer'?s\s+unit|this\s+unit)\s*,?\s+"
        r"have\s+(?:the\s+)?feel\s+no\s+pain\s*([1-6])\+)|"
        r"(?:while\s+a\s+character\s+model\s+is\s+leading\s+this\s+unit(?:\s*,\s*|\s+)that\s+character\s+model\s+has\s+"
        r"(?:the\s+)?feel\s+no\s+pain\s*([1-6])\+)",
        re.IGNORECASE,
    )
    _UNIT_CONTAINS_CHARACTER_FNP_RE = re.compile(
        r"while\s+this\s+unit\s+contains\s+an?\s+(?P<model>.+?)\s+model,\s*character\s+models\s+in\s+this\s+unit\s+"
        r"have\s+(?:a|the)?\s*feel\s+no\s+pain\s*(?P<value>[1-6])\+?(?:\s+ability)?",
        re.IGNORECASE,
    )
    _SAME_UNIT_KEYWORD_FNP_RE = re.compile(
        r"while\s+one\s+or\s+more\s+(?P<keyword>[a-z0-9][a-z0-9 '\-]*?)\s+models\s+are\s+in\s+the\s+same\s+unit\s+as\s+this\s+model,?\s*"
        r"those\s+(?P=keyword)\s+models\s+have\s+(?:a|the)?\s*feel\s+no\s+pain\s*(?P<value>[1-6])\+?(?:\s+ability)?",
        re.IGNORECASE,
    )
    _BEARER_UNIT_INVULNERABLE_SAVE_RE = re.compile(
        r"(?:models\s+in\s+)?(?:the\s+bearer'?s|that|this)\s+unit\s+(?:have|has)\s+(?:a|the)?\s*([1-6])\+?\s*invulnerable\s+save",
        re.IGNORECASE,
    )
    _UNIT_CONTAINS_INVULNERABLE_SAVE_RE = re.compile(
        r"while\s+this\s+unit\s+(?:is\s+leading\s+a\s+unit\s+and\s+)?contains\s+an?\s+(?P<model>.+?)\s+model,\s*"
        r"models\s+in\s+(?:the\s+bearer'?s|that|this)\s+unit\s+have\s+(?:a|the)?\s*(?P<value>[1-6])\+?\s*invulnerable\s+save",
        re.IGNORECASE,
    )
    _BEARER_WOUNDS_BONUS_RE = re.compile(
        r"add\s+(\d+)\s+to\s+the\s+bearer'?s\s+wounds?\s+characteristic",
        re.IGNORECASE,
    )
    _BEARER_WOUNDS_SET_RE = re.compile(
        r"(?:the\s+bearer|this\s+model)\s+has\s+a\s+wounds?\s+characteristic\s+of\s+(\d+)",
        re.IGNORECASE,
    )
    _BEARER_UNIT_AGILE_MANEUVER_REROLL_RE = re.compile(
        r"(?:you can )?re-?roll any rolls made for (?:the )?(?:bearer'?s|that) unit while it is performing an agile (?:manoeuvre|maneuver)",
        re.IGNORECASE,
    )
    _UNIQUE_MODEL_RESTRICTION_RE = re.compile(
        r"cannot include more than one of this (?:model|unit) in your army",
        re.IGNORECASE,
    )
    _BEARER_UNIT_SUSTAINED_HITS_RE = re.compile(
        r"(?:weapons?\s+equipped\s+by\s+models\s+in|models\s+in)\s+the\s+bearer'?s\s+unit.*?\bsustained\s+hits\b\s*(\d+)",
        re.IGNORECASE,
    )
    _BEARER_UNIT_IGNORES_COVER_RE = re.compile(
        r"(?:weapons?\s+equipped\s+by\s+models\s+in|attacks?\s+made\s+by\s+models\s+in)\s+"
        r"(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit|this\s+model'?s\s+unit).*?\bignores\s+cover\b",
        re.IGNORECASE,
    )
    _BEARER_UNIT_ASSAULT_RANGED_RE = re.compile(
        r"ranged\s+weapons?\s+equipped\s+by\s+models\s+in\s+"
        r"(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit|this\s+model'?s\s+unit).*?"
        r"\b(?:have|gain)\s+the\s+\[?assault\]?\s+ability\b",
        re.IGNORECASE,
    )
    _BEARER_UNIT_TARGET_HIT_PENALTY_RE = re.compile(
        r"each\s+time\s+(?:a|an)\s+(?:(?P<atype>melee|ranged)\s+)?attack(?:s)?\s+"
        r"(?:targets|is\s+made\s+against)\s+(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit),\s+"
        r"subtract\s+1\s+(?:from|form)\s+the\s+hit\s+roll",
        re.IGNORECASE,
    )
    _OBJECTIVE_RANGE_BENEFIT_OF_COVER_RE = re.compile(
        r"(?:while|if)\s+(?:this\s+unit|the\s+bearer'?s\s+unit|that\s+unit)\s+is\s+within\s+range\s+of\s+"
        r"(?:an|one\s+or\s+more)\s+objective\s+marker(?:s)?(?P<controlled>\s+you\s+control)?\s*,?\s*"
        r"each\s+time\s+(?:a|an)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+targets\s+"
        r"(?:this\s+unit|the\s+bearer'?s\s+unit|that\s+unit),?\s*models\s+in\s+"
        r"(?:it|that\s+unit|this\s+unit|the\s+bearer'?s\s+unit)\s+(?:have|gain)\s+the\s+benefit\s+of\s+cover",
        re.IGNORECASE,
    )
    _BEARER_UNIT_BENEFIT_OF_COVER_RE = re.compile(
        r"each\s+time\s+(?:a|an)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+targets\s+"
        r"(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit),?\s*models\s+in\s+"
        r"(?:it|that\s+unit|this\s+unit|the\s+bearer'?s\s+unit)\s+(?:have|gain)\s+the\s+benefit\s+of\s+cover",
        re.IGNORECASE,
    )
    _BEARER_UNIT_DEEP_STRIKE_RE = re.compile(
        r"models\s+in\s+(?:the\s+bearer'?s|that|this)\s+unit\s+have\s+the\s+deep\s+strike\s+ability",
        re.IGNORECASE,
    )
    _DEEP_STRIKE_AFFLICTED_DISTANCE_RE = re.compile(
        r"in your movement phase when this unit is set up on the battlefield using the deep strike ability "
        r"it can be set up anywhere on the battlefield that is more than (?P<afflicted>\d+) "
        r"(?:horizontally )?away from all afflicted enemy units and more than (?P<other>\d+) "
        r"(?:horizontally )?away from all other enemy units",
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
    _BEARER_LOSES_SMOKE_KEYWORD_TOKENS = "bearer loses the smoke keyword"
    _COMMAND_PHASE_BONUS_CP_RE = re.compile(
        r"(?:at\s+the\s+)?start\s+of\s+(?:each\s+of\s+)?your\s+command\s+phase[s]?\b.*?\bgain\s+(\d+)\s*(?:cp|command point(?:s)?)",
        re.IGNORECASE,
    )
    _COMMAND_PHASE_CP_ROLL_RE = re.compile(
        r"in\s+your\s+command\s+phase\s+if\s+this\s+(?:model|unit)\s+is\s+on\s+the\s+battlefield\s+roll\s+(?P<dice>\d+)d6\s+"
        r"on\s+a\s+(?P<threshold>\d+)\+?\s+you\s+gain\s+(?P<cp>\d+)\s*(?:cp|command\s+points?)",
        re.IGNORECASE,
    )
    _COMMAND_PHASE_REGAIN_WOUND_RE = re.compile(
        r"(?:at\s+the\s+)?start\s+of\s+(?:each\s+of\s+)?your\s+command\s+phase[s]?[,.]?\s*this\s+model\s+regains?\s+(\d+)\s+lost\s+wounds?",
        re.IGNORECASE,
    )
    _OPPONENT_TURN_STRATEGIC_RESERVES_RE = re.compile(
        r"(?:once per battle(?:,)?\s+)?(?:while this model is leading a unit )?at the end of your opponent(?:s|\s+s) turn if "
        r"(?:this unit|that unit|this model s unit|this models unit|the bearer s unit) "
        r"(?:(?:is wholly within (?P<edge_dist>\d+) of one or more battlefield edges? and )?"
        r"(?:(?:is\s+)?not within engagement range of one or more enemy units?|is more than (?P<min_dist>\d+) horizontally away from all enemy units?)"
        r"|(?:(?:is\s+)?not within engagement range of one or more enemy units?) and is wholly within (?P<edge_dist_alt>\d+) of one or more battlefield edges?) "
        r"you can remove (?:it|that unit|this unit) from the battlefield and place it into strategic reserves?",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_END_DESTROYED_STRATEGIC_RESERVES_RE = re.compile(
        r"at the end of the fight phase if (?:this unit|that unit|this model s unit|this models unit|the bearer s unit) "
        r"destroyed one or more enemy units this phase and is not within engagement range of one or more enemy units "
        r"you can remove (?:this unit|that unit) from the battlefield and place it into strategic reserves",
        re.IGNORECASE,
    )
    _OPPONENT_TURN_FRIENDLY_UNIT_DESTROYED_REPOSITION_RE = re.compile(
        r"once in each of your opponents turns if this model is on the battlefield when (?:another )?friendly "
        r"(?P<keyword>[a-z0-9 ]+) unit is destroyed just after removing the last model in that unit "
        r"you can remove this model from the battlefield and set it up as close as possible to where that destroyed model "
        r"was destroyed and not within engagement range of (?:one or more|any) enemy units?",
        re.IGNORECASE,
    )
    _TRANSPORT_REACTIVE_DISEMBARK_RE = re.compile(
        r"in your opponents movement phase each time an enemy unit is set up(?: on the battlefield)? or ends (?:a )?normal "
        r"advance or fall back move within (\d+) of this (?:model|unit) any units embarked within it can disembark",
        re.IGNORECASE,
    )
    _ENEMY_MOVE_REACTIVE_D6_RE = re.compile(
        r"once\s+per\s+(?:turn|battle|battle\s+round),?\s+when\s+an\s+enemy\s+unit\s+ends\s+a\s+normal(?:,)?\s+advance\s+or\s+fall\s+back\s+move\s+"
        r"within\s+(?P<range>\d+)\s*\"?\s+of\s+(?:this\s+(?:model(?: s)? unit|unit|model)|the\s+bearer'?s\s+unit|that\s+unit)"
        r"(?:\s+if\s+(?:this\s+unit|the\s+bearer'?s\s+unit|that\s+unit)\s+is\s+not\s+within\s+engagement\s+range\s+of\s+(?:one\s+or\s+more|any)\s+enemy\s+units?)?"
        r".*?make\s+a\s+normal\s+move\s+of\s+up\s+to\s+(?P<move>d\d+(?:\+\d+)?|\d+)",
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
        r"(?:this|that|the\s+bearer'?s)\s+unit\s+declares\s+a\s+charge"
        r".*?(?:if\s+one\s+or\s+more\s+targets?\s+of\s+that\s+charge\s+are|that\s+targets?\s+one\s+or\s+more\s+units?\s+that\s+are)"
        r"\s+within\s+range\s+of\s+(?:an|one\s+or\s+more)\s+objective\s+marker(?:s)?"
        r".*?re-?roll\s+the\s+charge\s+roll",
        re.IGNORECASE,
    )
    _UNIT_OBJECTIVE_CONTROLLED_FULL_WOUND_REROLL_RE = re.compile(
        r"while this unit is within range of (?:an|one or more) objective marker(?:s)? you control "
        r"you can re ?roll the wound roll instead",
        re.IGNORECASE,
    )
    _SELECTED_TO_SHOOT_CHARGE_REROLL_RE = re.compile(
        r"in your shooting phase each time this unit is selected to shoot if it makes one or more ranged attacks "
        r"and all of those attacks target the same enemy unit until the end of the turn each time this unit declares "
        r"a charge if that enemy unit is a target of that charge you can reroll the charge roll",
        re.IGNORECASE,
    )
    _ATTACK_TARGET_OBJECTIVE_KEYWORD_RE = re.compile(
        r"each\s+time\s+(?:this\s+(?:model|unit)|a\s+model\s+in\s+this\s+unit)\s+makes\s+(?:a|an)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+"
        r"that\s+targets\s+(?:an?\s+)?(?:enemy\s+)?unit\s+that\s+is\s+within\s+range\s+of\s+(?:an|one\s+or\s+more)\s+"
        r"objective\s+marker(?:s)?(?:,|\s+).*?that\s+attack\s+has\s+the\s+\[(?P<keyword>[^\]]+)\]\s+ability",
        re.IGNORECASE,
    )
    _ATTACK_TARGET_OBJECTIVE_KEYWORD_ON_CRIT_WOUND_RE = re.compile(
        r"each\s+time\s+(?:this\s+(?:model|unit)|a\s+model\s+in\s+(?:this\s+unit|that\s+unit|the\s+bearer'?s\s+unit))\s+"
        r"makes\s+(?:a|an)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+that\s+targets\s+(?:an?\s+)?(?:enemy\s+)?unit\s+"
        r"(?:that\s+is\s+)?within\s+range\s+of\s+(?:an|one\s+or\s+more)\s+objective\s+marker(?:s)?(?:\s*,\s*|\s+)"
        r"on\s+(?:a|an)\s+critical\s+wound(?:\s*,\s*|\s+)\s+that\s+attack\s+has\s+the\s+\[(?P<keyword>[^\]]+)\]\s+ability",
        re.IGNORECASE,
    )
    _ATTACK_TARGET_KEYWORD_BONUS_RE = re.compile(
        r"each\s+time\s+(?:this\s+(?:model|unit)|a\s+model\s+in\s+(?:this\s+unit|that\s+unit|the\s+bearer'?s\s+unit))\s+makes\s+"
        r"(?:a|an)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+that\s+targets\s+(?P<target_clause>.+?)(?:,|\s+)that\s+attack\s+has\s+"
        r"(?P<kw_section>.+?)\s+abilit",
        re.IGNORECASE,
    )
    _ATTACK_TARGET_HALF_RANGE_KEYWORD_RE = re.compile(
        r"each\s+time\s+(?:this\s+(?:model|unit)|a\s+model\s+in\s+this\s+unit)\s+makes\s+(?:a|an)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+"
        r"that\s+targets\s+(?:an?\s+)?(?:enemy\s+)?unit\s+within\s+half\s+range(?:,|\s+).*?"
        r"that\s+attack\s+has\s+the\s+\[(?P<keyword>[^\]]+)\]\s+ability",
        re.IGNORECASE,
    )
    _ATTACK_ALWAYS_KEYWORD_BONUS_RE = re.compile(
        r"each\s+time\s+(?:this\s+(?:model|unit)|a\s+model\s+in\s+(?:this\s+unit|that\s+unit|the\s+bearer'?s\s+unit))\s+makes\s+"
        r"(?:a|an)\s+(?:(?P<atype>melee|ranged)\s+)?attack(?:\s*,\s*|\s+)that\s+attack\s+has\s+(?P<kw_section>.+?)\s+abilit",
        re.IGNORECASE,
    )
    _WEAPON_LIST_HALF_RANGE_KEYWORD_RE = re.compile(
        r"this\s+model'?s\s+(?P<weapons>.+?)\s+(?:have|has)\s+the\s+\[(?P<keyword>[^\]]+)\]\s+ability.*?\bwithin\s+half\s+range\b",
        re.IGNORECASE,
    )
    _WEAPON_HALF_RANGE_KEYWORD_RE = re.compile(
        r"(?P<atype>melee|ranged)?\s*weapons?\s+equipped\s+by\s+(?:models\s+in\s+)?(?:this|that|the\s+bearer'?s)\s+unit.*?"
        r"\b(?:have|gain)\s+the\s+\[(?P<keyword>[^\]]+)\]\s+ability.*?\bwithin\s+half\s+range\b",
        re.IGNORECASE,
    )
    _WEAPON_HALF_RANGE_KEYWORD_MODEL_RE = re.compile(
        r"(?P<atype>melee|ranged)?\s*weapons?\s+equipped\s+by\s+this\s+model.*?"
        r"\b(?:have|gain)\s+the\s+\[(?P<keyword>[^\]]+)\]\s+ability.*?\bwithin\s+half\s+range\b",
        re.IGNORECASE,
    )
    _WEAPON_ALWAYS_KEYWORD_MODEL_RE = re.compile(
        r"(?P<atype>melee|ranged)?\s*weapons?\s+equipped\s+by\s+this\s+model.*?"
        r"\b(?:have|gain)\s+the\s+\[(?P<keyword>[^\]]+)\]\s+ability\b",
        re.IGNORECASE,
    )
    _BEARER_WEAPON_ALWAYS_KEYWORD_RE = re.compile(
        r"(?:the\s+bearer'?s|this\s+model'?s)\s+(?P<atype>melee|ranged)?\s*weapons?\s+"
        r"\b(?:have|has|gain)\s+the\s+\[(?P<keyword>[^\]]+)\]\s+ability\b",
        re.IGNORECASE,
    )
    _CHARGE_ROLL_TARGET_STRENGTH_BONUS_RE = re.compile(
        r"each\s+time\s+this\s+(?:model|unit)\s+declares\s+a\s+charge\s+that\s+targets?\s+one\s+or\s+more\s+units?\s+(?:that\s+are\s+)?"
        r"below\s+starting\s+strength\s+add\s+(?P<base>\d+)\s+to\s+the\s+charge\s+roll\s+if\s+one\s+or\s+more\s+of\s+"
        r"the\s+targets?\s+of\s+that\s+charge\s+are\s+below\s+half\s+strength\s+add\s+(?P<half>\d+)\s+to\s+the\s+charge\s+roll\s+instead",
        re.IGNORECASE,
    )
    _DEFENSIVE_CHARGE_ROLL_PENALTY_RE = re.compile(
        r"each\s+time\s+an?\s+enemy\s+unit\s+declares\s+a\s+charge\s+if\s+one\s+or\s+more\s+units?\s+with\s+this\s+ability\s+are\s+"
        r"selected\s+as\s+a\s+target\s+of\s+that\s+charge\s+subtract\s+(?P<val>\d+)\s+from\s+the\s+charge\s+roll",
        re.IGNORECASE,
    )
    _TARGETED_STRATAGEM_CP_DISCOUNT_RE = re.compile(
        r"once\s+per\s+battle\s+round\s+one\s+(?:unit|model)\s+from\s+your\s+army\s+with\s+this\s+ability\s+can\s+use\s+it\s+when\s+"
        r"(?:its\s+unit|this\s+models\s+unit|that\s+models\s+unit)\s+is\s+targeted\s+with\s+a\s+stratagem\s+"
        r"(?:if\s+it\s+does\s+)?reduce\s+the\s+cp\s+cost\s+of\s+that\s+(?:use|usage)\s+of\s+that\s+stratagem\s+by\s+1\s*cp",
        re.IGNORECASE,
    )
    _TARGETED_STRATAGEM_CP_DISCOUNT_SELECT_RE = re.compile(
        r"once\s+per\s+battle\s+round\s+you\s+can\s+select\s+one\s+model\s+from\s+your\s+army\s+with\s+this\s+ability\s+"
        r"(?:that\s+models\s+unit\s+can\s+be\s+targeted\s+with\s+a\s+stratagem|and\s+target\s+that\s+models\s+unit\s+with\s+a\s+stratagem)\s+"
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
    _TARGETED_STRATAGEM_CP_INCREASE_RANGE_RE = re.compile(
        r"within\s+(?P<range>\d+)\s+of\s+(?:this\s+model|the\s+bearer|this\s+unit)",
        re.IGNORECASE,
    )
    _TARGETED_STRATAGEM_CP_INCREASE_MAX_RE = re.compile(
        r"maximum\s+of\s+(?P<max>\d+)\s*cp",
        re.IGNORECASE,
    )
    _TARGETED_STRATAGEM_CP_REFUND_RE = re.compile(
        r"(?:the\s+bearer\s+loses\s+the\s+smoke\s+keyword\s+but\s+)?"
        r"each\s+time\s+you\s+target\s+"
        r"(?P<subject>this\s+unit|that\s+unit|the\s+bearer|the\s+bearers\s+unit|the\s+bearer\s+s\s+unit|"
        r"this\s+models\s+unit|this\s+model\s+s\s+unit)\s+"
        r"with\s+a\s+stratagem\s+roll\s+one\s+d6\s+on\s+a\s+(?P<roll>\d+)\s+"
        r"(?:you\s+)?gain\s+(?P<cp>\d+)\s*cp",
        re.IGNORECASE,
    )
    _TARGETED_STRATAGEM_CP_REFUND_SELECT_RE = re.compile(
        r"each\s+time\s+you\s+select\s+"
        r"(?P<subject>the\s+bearers\s+unit|the\s+bearer\s+s\s+unit|this\s+models\s+unit|this\s+model\s+s\s+unit|"
        r"its\s+unit|that\s+unit|this\s+unit)\s+"
        r"as\s+the\s+target\s+of\s+a\s+stratagem\s+roll\s+one\s+d6\s+on\s+a\s+(?P<roll>\d+)\s+"
        r"(?:you\s+)?gain\s+(?P<cp>\d+)\s*cp",
        re.IGNORECASE,
    )
    _POST_SHOOT_BATTLESHOCK_RE = re.compile(
        r"in your shooting phase(?: and the fight phase)? after this (?P<subject>model|unit) has shot(?: or fought)? "
        r"select one enemy (?:(?P<infantry>infantry) )?unit "
        r"(?:\((?:excluding|except) (?P<exclude_paren>[a-z0-9 ]+)\) )?"
        r"(?:excluding (?P<exclude>[a-z0-9 ]+) )?"
        r"(?:that was )?hit by one or more of those attacks that (?:enemy )?unit must take a battle shock test",
        re.IGNORECASE,
    )
    _POST_SHOOT_BATTLESHOCK_PENALTY_RE = re.compile(
        r"in your shooting phase after this (?P<subject>model|unit) has shot select one enemy unit "
        r"(?:excluding monsters and vehicles )?hit by one or more of those attacks "
        r"(?:made with (?:a|an|the|its) [a-z0-9 ]+ )?"
        r"that (?:enemy )?unit must take a battle shock test subtracting (?P<pen>\d+) from the result",
        re.IGNORECASE,
    )
    _POST_SHOOT_BATTLESHOCK_ON_KILL_RE = re.compile(
        r"in your shooting phase after this (?P<subject>model|unit) has shot select one enemy unit "
        r"(?:excluding monsters and vehicles )?hit by one or more of those attacks "
        r"that (?:enemy )?unit must take a battle shock test "
        r"if one or more of those attacks destroyed a model in that enemy unit "
        r"subtract (?P<pen>\d+) from that test",
        re.IGNORECASE,
    )
    _POST_SHOOT_OR_FIGHT_BATTLESHOCK_CONDITIONAL_RE = re.compile(
        r"in your shooting phase and the fight phase after this (?P<subject>model|unit) has shot or fought "
        r"select one enemy unit hit by one or more of those attacks that (?:enemy )?unit must take a battle shock test "
        r"subtracting (?P<pen>\d+) from that test if it is within (?P<range>\d+) of one or more "
        r"(?P<friendly>[a-z0-9 ]+) units from your army",
        re.IGNORECASE,
    )
    _ON_KILL_BATTLESHOCK_WITHIN_RANGE_RE = re.compile(
        r"each time an enemy unit is destroyed as (?:a|the) result of this (?P<subject>model|unit)(?: s|s)? attacks? "
        r"before removing the last model in that unit from the battlefield "
        r"(?:each unit from your opponent(?: s|s)? army|each enemy unit) that (?:is )?within (?P<range>\d+) of it "
        r"must take a battle shock test",
        re.IGNORECASE,
    )
    _POST_SHOOT_DISEMBARK_WOUND_REROLL_RE = re.compile(
        r"in your shooting phase after this model has shot select one enemy unit "
        r"(?:(?:that was )?hit by one or more of those attacks|it scored one or more hits against this phase) "
        r"until the end of the phase each time a friendly model that disembarked from this transport this turn makes an attack "
        r"that targets that enemy unit you can re ?roll the wound roll",
        re.IGNORECASE,
    )
    _POST_SHOOT_DISEMBARK_AP_BONUS_RE = re.compile(
        r"in your shooting phase after this model has shot select one enemy unit hit by one or more of those attacks "
        r"until the end of the turn each time a friendly model that disembarked from this transport this turn makes an attack "
        r"that targets that enemy unit improve the armou?r penetration characteristic of that attack by (?P<val>\d+) "
        r"the same enemy unit can only be affected by this ability once per turn",
        re.IGNORECASE,
    )
    _POST_SHOOT_DISEMBARK_PSYCHIC_HIT_WOUND_BONUS_RE = re.compile(
        r"in your shooting phase after this model has shot select one enemy unit hit by one or more of those attacks "
        r"until the end of the phase each time a friendly model that disembarked from this transport this turn makes a psychic attack "
        r"that targets that enemy unit add (?P<hit>\d+) to the hit roll and add (?P<wound>\d+) to the wound roll",
        re.IGNORECASE,
    )
    _AMMO_RUNT_RE = re.compile(
        r"once per battle(?P<per_runt> for each ammo runt this unit has)? when this unit is selected to shoot "
        r"it can use this ability if it does until the end of the phase ranged weapons equipped by models in this unit "
        r"have the lethal hits ability(?: .*)?",
        re.IGNORECASE,
    )
    _BOMB_SQUIGS_RE = re.compile(
        r"once per battle for each bomb squig this unit has after this unit ends a normal move "
        r"you can use one bomb squig if you do select one enemy unit within (?P<range>\d+) and visible to this unit "
        r"and roll (?:one|1) d6 on a (?P<threshold>\d)\+? that enemy unit suffers (?P<mw>d3|d6|\d+) mortal wounds?"
        r"(?: designers note .+)?",
        re.IGNORECASE,
    )
    _HAND_OF_ASURYAN_RE = re.compile(
        r"once per battle when this model is selected to shoot it can use this ability if it does until the end of the phase "
        r"its (?P<weapon>[a-z0-9 ]+?) weapon has a damage characteristic of (?P<damage>\d+)",
        re.IGNORECASE,
    )
    _SHIELDBREAKER_RE = re.compile(
        r"once per battle when selecting targets for this model s (?P<weapon>[a-z0-9 ]+?) "
        r"it can fire a shieldbreaker round if it does until the end of the phase each time this model makes an attack "
        r"with that weapon add (?P<wound>\d+) to the wound roll and any successful wound roll scores a critical wound",
        re.IGNORECASE,
    )
    _HARVESTER_OF_SOULS_RE = re.compile(
        r"while this model is leading a unit in your shooting phase after selecting targets for that unit s attacks "
        r"if every attack targets the same unit roll one d6 for the target unit and one d6 for every other enemy unit within "
        r"(?P<range>\d+) of the target unit on a (?P<threshold>\d)\+ the unit being rolled for is struck by explosive debris "
        r"after resolving all of that unit s attacks against the target unit each unit struck by explosive debris suffers d3 mortal wounds",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_ENGAGEMENT_WOUND_REROLL_ONES_RE = re.compile(
        r"at the start of the fight phase select one enemy unit within engagement range of this model "
        r"until the end of the phase each time a friendly (?P<keyword>[a-z0-9 ]+) model makes an attack that targets that unit "
        r"you can re ?roll a wound roll of 1",
        re.IGNORECASE,
    )
    _MOVEMENT_PHASE_END_MISFORTUNE_RE = re.compile(
        r"at the end of your movement phase select one enemy unit within (?P<range>\d+) of and visible to this model "
        r"until the start of your next command phase each time a model in that unit makes an attack subtract (?P<pen>\d+) "
        r"from the wound roll(?: each unit can only be selected for this ability once per turn)?",
        re.IGNORECASE,
    )
    _MOVEMENT_PHASE_END_TOUGHNESS_PENALTY_RE = re.compile(
        r"at the end of your movement phase you can select one enemy unit within (?P<range>\d+) of this model "
        r"until the start of your next movement phase (?:subtract (?P<pen>\d+) from the toughness characteristic of models in that unit|"
        r"that unit is rotted while a unit is rotted subtract (?P<pen_alt>\d+) from the toughness characteristic of models in that unit)",
        re.IGNORECASE,
    )
    _MOVEMENT_PHASE_END_BATTLESHOCK_REROLL_RE = re.compile(
        r"at the end of your movement phase you can select one enemy unit that is battle shocked and within (?P<range>\d+) of this model "
        r"until the end of the turn each time a (?P<keywords>[a-z0-9 ]+) model from your army makes an attack that targets that enemy unit "
        r"you can re roll the hit roll and you can re roll the wound roll",
        re.IGNORECASE,
    )
    _MOVEMENT_PHASE_END_SHADOW_OF_CHAOS_TERRAIN_RE = re.compile(
        r"at the end of your movement phase if this model is within one area terrain feature until the end of the battle "
        r"that area terrain feature is considered to be within your army s shadow of chaos",
        re.IGNORECASE,
    )
    _START_SHOOTING_PHASE_DEATH_HEX_RE = re.compile(
        r"at the start of your shooting phase one psyker with this ability can use it if it does "
        r"select one enemy unit within (?P<range>\d+) of and visible to that psyker and roll (?:one|1) d6 "
        r"on a 1 that psyker s unit suffers d3 mortal wounds on a 2\+? until the start of your next movement phase "
        r"each time an attack targets that enemy unit improve the (?:armour|armor) penetration characteristic of that attack by (?P<ap>\d+)",
        re.IGNORECASE,
    )
    _START_SHOOTING_PHASE_VISIBLE_BATTLESHOCK_RE = re.compile(
        r"at the start of your shooting phase select one enemy unit within (?P<range>\d+) (?:of )?and visible to this model "
        r"that enemy unit must take a battle shock test",
        re.IGNORECASE,
    )
    _START_SHOOTING_PHASE_VISIBLE_HIT_BONUS_RE = re.compile(
        r"at the start of your shooting phase select one enemy unit that is visible to this psyker model "
        r"until the end of the phase each time a model in this unit makes an attack that targets that enemy unit "
        r"add (?P<val>\d+) to the hit roll",
        re.IGNORECASE,
    )
    _START_SHOOTING_PHASE_BLIGHT_BOMBARDMENT_RE = re.compile(
        r"at the start of your shooting phase select one enemy unit within (?P<range>\d+) of and visible to this model "
        r"until the end of the phase each time a friendly death guard model makes a ranged attack that targets that unit "
        r"re roll a hit roll of 1 if that attack is made with a blast weapon you can re roll the hit roll instead",
        re.IGNORECASE,
    )
    _SHOOTING_PHASE_EATER_PLAGUE_RE = re.compile(
        r"in your shooting phase you can select one enemy unit within (?P<range>\d+) of and visible to this psyker "
        r"excluding units with the lone operative ability that are not part of an attached unit and are not within (?P<lone_range>\d+) of this psyker "
        r"and roll (?:one|1) d6 on a 1 this psyker s unit suffers d3 mortal wounds on a 2 5 that enemy unit suffers d6 mortal wounds "
        r"on a 6 that enemy unit suffers d3 3 mortal wounds",
        re.IGNORECASE,
    )
    _RANGED_ATTACK_PSYCHIC_HIT_MONSTER_VEHICLE_HIT_DAMAGE_REROLL_RE = re.compile(
        r"each time this model makes a ranged attack that targets a monster or vehicle unit that was hit by one or more psychic attacks "
        r"made by a thousand sons psyker model from your army this phase including the doombolt ritual "
        r"you can re roll the hit roll and you can re roll the damage roll",
        re.IGNORECASE,
    )
    _RANGED_ATTACK_PSYCHIC_HIT_NONMONSTER_NONVEHICLE_STRENGTH_AP_BONUS_RE = re.compile(
        r"each time this model makes a ranged attack that targets a unit excluding monsters and vehicles "
        r"that was hit by one or more psychic attacks made by a thousand sons psyker model from your army this phase "
        r"including the doombolt ritual improve the strength and armour penetration characteristics of that attack by (?P<val>\d+)",
        re.IGNORECASE,
    )
    _DESTROYER_OF_FUTURES_OVERWATCH_RE = re.compile(
        r"each time you target this unit with the fire overwatch stratagem hits are scored on unmodified hit rolls of (?P<base>\d)(?:\+)? "
        r"when resolving that stratagem for each of those attacks that targets an enemy unit within (?P<range>\d+) "
        r"of one or more thousand sons psyker units from your army a hit is scored on an unmodified hit roll of (?P<near>\d)(?:\+)? instead",
        re.IGNORECASE,
    )
    _FORTIFY_OVERWATCH_RE = re.compile(
        r"each time you target this unit with the fire overwatch stratagem hits are scored on unmodified hit rolls of (?P<base>\d)(?:\+)? "
        r"(?:when|while) resolving that stratagem if units from your army have fortify takeover hits are scored on unmodified hit rolls "
        r"of (?P<fortify>\d)(?:\+)? while resolving that stratagem instead",
        re.IGNORECASE,
    )
    _PROPHETIC_SENTINELS_STRATAGEM_RE = re.compile(
        r"once per battle round (?:this (?:model|unit) can use this ability if it does )?"
        r"you can target this unit with the fire overwatch or heroic intervention stratagem for 0cp",
        re.IGNORECASE,
    )
    _SNARLING_PROTECTOR_HEROIC_RE = re.compile(
        r"you can target this model with the heroic intervention stratagem for 0cp and can do so even if you have already targeted "
        r"a different unit with that stratagem this phase",
        re.IGNORECASE,
    )
    _SNARLING_PROTECTOR_CHARGE_REROLL_RE = re.compile(
        r"in addition each time this model declares a charge that targets an enemy unit within engagement range of one or more "
        r"thousand sons psyker units from your army you can re roll the charge roll",
        re.IGNORECASE,
    )
    _START_SHOOTING_PHASE_SPIRIT_THIEF_RE = re.compile(
        r"at the start of your shooting phase select one visible enemy vehicle unit until the end of the phase "
        r"each time a friendly heretic astartes model makes an attack that targets that unit re roll a wound roll of 1",
        re.IGNORECASE,
    )
    _START_SHOOTING_PHASE_CORRUPT_MACHINE_SPIRITS_RE = re.compile(
        r"at the start of your shooting phase select one visible enemy vehicle unit within (?P<range>\d+) of this model and roll "
        r"(?:one|1) d6 on a 2 3 that enemy unit suffers d3 mortal wounds on a 4 5 that enemy unit suffers 3 mortal wounds "
        r"on a 6 that enemy unit suffers d3 3 mortal wounds",
        re.IGNORECASE,
    )
    _START_OPP_SHOOTING_PHASE_MISCHIEF_CONFUSION_RE = re.compile(
        r"at the start of your opponent s shooting phase select one enemy unit within (?P<range>\d+) of and visible to this model "
        r"and roll (?:one|1) d6 on a 2 5 until the end of the phase each time a model in that enemy unit makes an attack "
        r"subtract 1 from the hit roll on a 6 that enemy unit is not eligible to shoot this phase",
        re.IGNORECASE,
    )
    _START_OPP_SHOOTING_PHASE_HORRIBLE_FASCINATION_RE = re.compile(
        r"at the start of your opponent s shooting phase one psyker model from your army with this ability can use it if it does "
        r"select one enemy unit within (?P<range>\d+) of and visible to that psyker model and roll (?:one|1) d6 "
        r"on a 1 that psyker model suffers d3 mortal wounds on a 2 5 until the end of the phase each time a model in that enemy unit "
        r"makes an attack subtract 1 from the hit roll on a 6 that enemy unit is not eligible to shoot this phase",
        re.IGNORECASE,
    )
    _START_OPP_SHOOTING_PHASE_TREASON_HAZARDOUS_RE = re.compile(
        r"at the start of your opponent s shooting phase select one enemy unit within (?P<range>\d+) "
        r"(?:of and visible to|of) this psyker until the end of the phase ranged weapons equipped by models in that unit "
        r"have the hazardous ability",
        re.IGNORECASE,
    )
    _START_OPP_SHOOTING_PHASE_FRIENDLY_VISIBLE_STEALTH_RE = re.compile(
        r"at the start of your opponent s shooting phase this unit can use this ability if it does select one "
        r"(?P<keyword>[a-z0-9 ]+) unit from your army (?:that is )?visible to and within (?P<range>\d+) of this unit "
        r"until the end of the phase that unit has the stealth ability",
        re.IGNORECASE,
    )
    _MOVEMENT_PHASE_END_ENEMY_WITHIN_RANGE_MORTAL_TABLE_RE = re.compile(
        r"at the end of your movement phase roll (?:one|1) d6 for each enemy unit within (?P<range>\d+) of this model "
        r"on a 2 3 that unit suffers 1 mortal wounds? on a 4 5 that unit suffers d3 mortal wounds? on a 6 that unit suffers d6 mortal wounds?"
        r"(?: each enemy unit within range of this ability must then take a battle shock test)?",
        re.IGNORECASE,
    )
    _MOVEMENT_PHASE_END_ENEMY_WITHIN_RANGE_MORTAL_THRESHOLD_RE = re.compile(
        r"at the end of your movement phase roll (?:one|1) d6 for each enemy unit within (?P<range>\d+) of "
        r"(?:(?:this model)|(?:one or more models(?: from your army)?(?: with this ability)?(?: from your army)?)) "
        r"(?:(?:adding (?P<bonus_pre>\d+) to the result if that (?:enemy )?unit is afflicted) )?"
        r"on a (?P<threshold>\d)\+? "
        r"(?:(?:adding (?P<bonus_mid>\d+) to the result if that (?:enemy )?unit is afflicted) )?"
        r"that enemy unit suffers (?P<mw>d3|d6|\d+) mortal wounds?"
        r"(?: adding (?P<bonus_post>\d+) to the result if that (?:enemy )?unit is afflicted)?",
        re.IGNORECASE,
    )
    _POST_SHOOT_MONSTER_VEHICLE_MORTAL_THRESHOLD_RE = re.compile(
        r"in your shooting phase after this model has shot select one enemy monster or vehicle unit hit by one or more of those attacks "
        r"roll (?:one|1) d6(?: adding (?P<bonus>\d+) to the result if that unit is afflicted)? on a (?P<threshold>\d)\+? "
        r"that unit suffers (?P<mw>d3|d6|\d+) mortal wounds?",
        re.IGNORECASE,
    )
    _POINT_BLANK_DEVASTATION_RE = re.compile(
        r"each time this model s (?P<weapon1>[a-z0-9 ]+?) or (?P<weapon2>[a-z0-9 ]+?) targets a unit within half range "
        r"you can re ?roll the dice to determine the number of attacks made",
        re.IGNORECASE,
    )
    _FLEET_OF_FOOT_RE = re.compile(
        r"this unit can perform the fade back agile manoeuvre without spending a battle focus token to do so "
        r"it can do so even if other units have done so in the same phase and doing so does not prevent other units "
        r"from performing the same agile manoeuvre in the same phase",
        re.IGNORECASE,
    )
    _POST_SHOOT_CRIT_HIT_THRESHOLD_RE = re.compile(
        r"in your shooting phase after this model has shot select one enemy unit hit by one or more of those attacks "
        r"until the end of the turn each time a friendly (?P<keyword>[a-z0-9 ]+) model makes an attack that targets that unit "
        r"an unmodified hit roll of (?P<threshold>\d)\+? scores a critical hit",
        re.IGNORECASE,
    )
    _SONIC_DESTRUCTION_RE = re.compile(
        r"in your shooting phase each time this model makes an attack with its (?P<weapon>[a-z0-9 ]+) that targets an enemy unit "
        r"improve the strength armour penetration and damage characteristics of that attack by (?P<val>\d+) "
        r"for each other friendly (?P<platform>[a-z0-9 ]+) model that made one or more attacks with its (?P<weapon2>[a-z0-9 ]+) "
        r"that also targeted that enemy unit this phase",
        re.IGNORECASE,
    )
    _MELEE_CHARGE_STRENGTH_DAMAGE_RE = re.compile(
        r"each time a model in (?:this|that) unit makes (?:a|an)? melee attack(?:s)? "
        r"if (?:this|that) unit made a charge move this turn "
        r"improve the strength and damage characteristic(?:s)? of that attack by (?P<val>\d+)",
        re.IGNORECASE,
    )
    _MELEE_CHARGE_STRENGTH_ONLY_RE = re.compile(
        r"each time a model in (?:this|that) unit makes (?:a|an)? melee attack(?:s)? "
        r"if (?:this|that) unit made a charge move this turn "
        r"improve the strength characteristic(?:s)? of that attack by (?P<val>\d+)",
        re.IGNORECASE,
    )
    _MELEE_CHARGE_DAMAGE_ONLY_MODEL_KEYWORD_RE = re.compile(
        r"each time this unit makes a charge move until the end of the turn add (?P<val>\d+) to the damage characteristic "
        r"of melee weapons equipped by (?P<keyword>[a-z0-9 ]+) models in this unit",
        re.IGNORECASE,
    )
    _SPIRIT_MARK_RE = re.compile(
        r"once per turn in your movement phase when this model starts or ends a move select one friendly (?P<keyword>[a-z0-9 ]+) unit within "
        r"(?P<range>\d+)\s*\"?\s*of this model(?: excluding titanic units)? and one enemy unit visible to this model "
        r"until the start of your next movement phase weapons equipped by models in that friendly unit have the sustained hits (?P<val>\d+) ability "
        r"while targeting that enemy unit",
        re.IGNORECASE,
    )
    _TEARS_OF_ISHA_RE = re.compile(
        r"in your command phase select one friendly (?P<keyword>[a-z0-9 ]+) unit within (?P<range>\d+)\s*\"?\s*of this model "
        r"if one or more models in that unit are destroyed you can return one destroyed model to that unit "
        r"otherwise one model in that unit regains up to d3 lost wounds each unit can only be selected for this ability once per turn",
        re.IGNORECASE,
    )
    _WORD_OF_PHOENIX_RE = re.compile(
        r"while this model is leading a unit in your command phase roll one d6 on a 2\+ d3\+1 destroyed bodyguard models "
        r"\(excluding support weapon models\) are returned to that unit with their full wounds remaining",
        re.IGNORECASE,
    )
    _TACTICAL_ACUMEN_RE = re.compile(
        r"while this model is leading a unit in your shooting phase after that unit has shot it can make a normal move of up to "
        r"(?P<range>\d+)\s*\"?\s*if it does until the end of the turn that unit is not eligible to declare a charge",
        re.IGNORECASE,
    )
    _POST_SHOOT_REACTIVE_MOVE_NO_CHARGE_RE = re.compile(
        r"in your shooting phase after this unit has shot(?: if it is not within engagement range of one or more enemy units)? "
        r"it can make a normal move of up to (?P<range_expr>d6|\d+)\s*\"?\s*if it does until the end of the turn this unit is not eligible to declare a charge",
        re.IGNORECASE,
    )
    _SHADOW_FIELD_RE = re.compile(
        r"you cannot re roll invulnerable saving throws made for the bearer the first time an invulnerable saving throw made for the bearer is failed "
        r"until the end of the battle the bearer has no invulnerable save",
        re.IGNORECASE,
    )
    _POST_SHOOT_INFANTRY_MW_BATTLESHOCK_RE = re.compile(
        r"in your shooting phase after this model s unit has shot select one enemy infantry unit hit by one or more of those attacks "
        r"and roll (?P<dice>three|3) d6 for each 4 that enemy unit suffers 1 mortal wounds? "
        r"if an enemy unit suffers one or more mortal wounds as a result of this ability it must take a battle shock test",
        re.IGNORECASE,
    )
    _POST_SHOOT_SUPPRESSION_RE = re.compile(
        r"in your shooting phase after this (?:model|unit) has shot select one enemy unit "
        r"(?:(?P<exclude>excluding monsters and vehicles) )?hit by one or more of those attacks "
        r"(?:made with (?:(?:a|an|the|its)\s+)?(?P<weapon>[a-z0-9 ]+) )?"
        r"(?:excluding monsters and vehicles )?until the start of your next turn that enemy unit is suppressed "
        r"while a unit is suppressed each time a model in that unit makes an attack subtract 1 from the hit roll",
        re.IGNORECASE,
    )
    _POST_SHOOT_AFFLICTED_RE = re.compile(
        r"in your shooting phase (?:each time this (?:model|unit) is selected to shoot )?after this (?:model|unit) has shot "
        r"select one enemy unit hit by one or more of those attacks until the start of your next turn that enemy unit is afflicted",
        re.IGNORECASE,
    )
    _POST_SHOOT_SNARE_RE = re.compile(
        r"in your shooting phase after this model has shot select one enemy unit hit by one or more of those attacks made with "
        r"(?:a|an|the|its) (?P<weapon>[a-z0-9 ]+) until the start of your next turn that enemy unit is snared "
        r"while a unit is snared each time that unit makes a normal advance or fall back move roll (?:one|1) d6 for each model in that unit "
        r"for each 1 that unit suffers 1 mortal wounds?",
        re.IGNORECASE,
    )
    _POST_SHOOT_PINNED_RE = re.compile(
        r"in your shooting phase after this model has shot if one or more of those attacks made with its (?P<weapon>[a-z0-9 ]+) "
        r"scored a hit against an enemy unit until the start of your next turn that enemy unit is pinned "
        r"while a unit is pinned subtract (?P<move>\d+) from that unit s move characteristic and subtract (?P<charge>\d+) "
        r"from charge rolls made for it",
        re.IGNORECASE,
    )
    _POST_SHOOT_PINNED_ALT_RE = re.compile(
        r"in your shooting phase after this model has shot select one enemy (?:(?P<infantry>infantry) )?unit "
        r"hit by one or more of those attacks made with (?:(?:a|an|the|its)\s+)?(?P<weapon>[a-z0-9 ]+) "
        r"until the start of your next turn that unit is (?:pinned|ensnared) while a unit is (?:pinned|ensnared) "
        r"subtract (?P<move>\d+) from (?:that unit s|its) move characteristic and subtract (?P<charge>\d+) from charge rolls made for it",
        re.IGNORECASE,
    )
    _POST_SHOOT_PINNED_UNIT_RE = re.compile(
        r"in your shooting phase after this unit has shot select one enemy unit "
        r"(?:(?P<exclude>excluding monsters and vehicles) )?hit by one or more of those attacks "
        r"until the start of your next turn that enemy unit is pinned while a unit is pinned subtract (?P<move>\d+) from that unit s move characteristic "
        r"and subtract (?P<charge>\d+) from charge rolls made for it",
        re.IGNORECASE,
    )
    _POST_SHOOT_AFLAME_RE = re.compile(
        r"in your shooting phase after this model has shot select one enemy unit "
        r"(?:(?P<exclude>excluding monsters and vehicles) )?hit by one or more of those attacks "
        r"(?:and )?roll (?:one|1) d6 on a (?P<threshold>\d)\+? "
        r"until the end of your opponent s next turn that enemy unit is aflame "
        r"while a unit is aflame subtract (?P<move>\d+) from its move characteristic and subtract "
        r"(?P<advance>\d+) from advance and charge rolls made for it",
        re.IGNORECASE,
    )
    _POST_SHOOT_NO_COVER_WEAPON_RE = re.compile(
        r"in your shooting phase after this unit has shot select one enemy unit hit by one or more of those attacks made with "
        r"(?:a|an|the) (?P<weapon>[a-z0-9 ]+) until the (?P<duration>end of the phase|start of your next shooting phase) "
        r"that enemy unit cannot have the benefit of cover",
        re.IGNORECASE,
    )
    _POST_SHOOT_NO_COVER_RE = re.compile(
        r"in your shooting phase after this (?:model|unit) has shot select one enemy unit (?:that was )?hit by one or more of those attacks "
        r"until the (?P<duration>end of the phase|start of your next shooting phase) that (?:enemy )?unit cannot have the benefit of cover",
        re.IGNORECASE,
    )
    _POST_SHOOT_NO_OVERWATCH_WEAPON_RE = re.compile(
        r"in your shooting phase after this unit has shot select one enemy unit (?:excluding monsters and vehicles )?"
        r"hit by one or more of those attacks made with (?:a|an|the|its) (?P<weapon>[a-z0-9 ]+) "
        r"until the start of your next shooting phase that enemy unit cannot be targeted with the fire overwatch stratagem",
        re.IGNORECASE,
    )
    _POST_SHOOT_KEYWORD_WOUND_REROLL_RE = re.compile(
        r"in your shooting phase after this (?:model|unit) has shot select one enemy unit hit by one or more of those attacks "
        r"until the end of the turn each time a friendly (?P<keyword>[a-z0-9 ]+) unit makes an attack that targets that unit "
        r"you can re ?roll the wound roll",
        re.IGNORECASE,
    )
    _POST_SHOOT_KEYWORD_HIT_BONUS_RE = re.compile(
        r"in your shooting phase after this unit has shot select one enemy unit hit by one or more of those attacks "
        r"until the end of the phase each time a (?:(?:friendly )?(?P<keyword>[a-z0-9 ]+) model(?: from your army)?|model from your army) makes an attack that targets that unit "
        r"add (?P<val>\d+) to the hit roll",
        re.IGNORECASE,
    )
    _POST_SHOOT_MODEL_WEAPON_KEYWORD_STRENGTH_BONUS_RE = re.compile(
        r"in your shooting phase after this model s unit has shot select one enemy unit hit by one or more (?:of those )?attacks made with this model s (?P<weapon>[a-z0-9 ]+) "
        r"until the end of the turn that unit is riven each time an (?:(?:friendly )?(?P<keyword>[a-z0-9 ]+) model(?: from your army)?|model from your army) makes an attack that targets a riven unit "
        r"add (?P<val>\d+) to the strength characteristic of that attack",
        re.IGNORECASE,
    )
    _POST_SHOOT_WRACKING_AGONIES_RE = re.compile(
        r"in your shooting phase after this model has shot select one infantry unit hit by one or more of those attacks "
        r"made with its (?P<weapon>[a-z0-9 ]+) until the start of your next turn that unit is wracked with agonies "
        r"while a unit is wracked with agonies subtract (?P<move>\d+) from its move characteristic and subtract (?P<charge>\d+) "
        r"from charge rolls made for it",
        re.IGNORECASE,
    )
    _POST_SHOOT_ENFEEBLED_RE = re.compile(
        r"in your shooting phase after this model has shot select one enemy infantry unit hit by one or more of those attacks "
        r"made with (?:its|this model s) (?P<weapon>[a-z0-9 ]+) until the end of your opponent s next turn that unit is enfeebled "
        r"while a unit is enfeebled subtract (?P<move>\d+) from the move characteristic of models in that unit",
        re.IGNORECASE,
    )
    _POST_SHOOT_LEADERSHIP_DEBUFF_RE = re.compile(
        r"in your shooting phase after this unit has shot select one enemy unit hit by one or more of those attacks "
        r"until the start of your next shooting phase each time a battle shock or leadership test is taken for that "
        r"(?:enemy )?unit subtract 1 from that test",
        re.IGNORECASE,
    )
    _POST_SHOOT_AP_BONUS_RE = re.compile(
        r"in your shooting phase after this (?:unit|model) has shot select one enemy unit "
        r"(?:(?P<exclude>excluding monsters and vehicles) )?hit by one or more of those attacks "
        r"until the end of the phase each time a friendly (?P<keyword>[a-z0-9 ]+?) unit makes (?:a|an) (?:(?P<atype>ranged|melee) )?attack "
        r"that targets that enemy unit improve the armou?r penetration characteristic of that attack by (?P<val>\d+)"
        r"(?: the same enemy unit can only be affected by this ability once per (?:turn|phase)| each unit can only be selected for this ability once per turn)?",
        re.IGNORECASE,
    )
    _POST_SHOOT_SHOOT_AGAIN_RE = re.compile(
        r"once per battle in your shooting phase after this unit has shot it can shoot again",
        re.IGNORECASE,
    )
    _RANGED_TARGETING_RESTRICTION_RE = re.compile(
        r"(?:can only be selected as the target of (?:a )?ranged attacks? if the attacking model is within (?P<range>\d+)"
        r"|cannot be targeted by ranged attacks unless the attacking model is within (?P<range2>\d+))",
        re.IGNORECASE,
    )
    _DAEMONIC_POISONS_RE = re.compile(
        r"in your shooting phase and the fight phase after this model has finished making its attacks "
        r"select one enemy unit hit by one or more of those attacks until the end of the battle that enemy unit "
        r"is poisoned at the start of each player s command phase roll one d6 for each poisoned enemy unit "
        r"on the battlefield on a 4 that enemy unit suffers d3 mortal wounds",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_ENGAGEMENT_BATTLESHOCK_RE = re.compile(
        r"at the start of the fight phase each enemy unit within engagement range of this model must take a battle shock test"
        r"(?: subtracting (?P<penalty>\d+) from (?:that test|the result) if that enemy unit is below half strength)?",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_ENGAGEMENT_BATTLESHOCK_UNIT_RE = re.compile(
        r"at the start of the fight phase each enemy unit within engagement range of one or more units "
        r"(?:from your army )?with this ability must take a battle shock test"
        r"(?: subtracting (?P<penalty>\d+) from the result if that enemy unit is below half strength)?",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_RANGE_BATTLESHOCK_RE = re.compile(
        r"at the start of the fight phase (?:each|every) enemy unit(?: excluding (?P<exclude>[a-z0-9 ]+?))? within "
        r"(?P<range>\d+)\s*\"?\s*of this model must take a battle shock test",
        re.IGNORECASE,
    )
    _OPPONENT_COMMAND_PHASE_BELOW_STARTING_BATTLESHOCK_RE = re.compile(
        r"(?:while an enemy unit is within (?P<range_alt>\d+)\s*\"?\s*of this model(?:,)?\s+)?"
        r"in the battle shock step of your opponent s command phase if "
        r"(?:an enemy unit that is below its starting strength is within (?P<range>\d+)\s*\"?\s*of this model|"
        r"such an enemy unit is below its starting strength) "
        r"(?:that enemy unit|it) must take a battle shock test"
        r"(?: subtracting (?P<pen>\d+) from that test if it is a psyker unit)?",
        re.IGNORECASE,
    )
    _START_ANY_COMMAND_PHASE_ENEMY_RANGE_BATTLESHOCK_RE = re.compile(
        r"once per battle at the start of any command phase this model can use this ability if it does "
        r"each enemy unit within (?P<range>\d+)\s*\"?\s*of this model must take a battle shock test "
        r"subtracting (?P<pen>\d+) from that test(?: or subtracting (?P<psyker_pen>\d+) if that unit is a psyker)?",
        re.IGNORECASE,
    )
    _CHARGE_END_ENGAGEMENT_BATTLESHOCK_RE = re.compile(
        r"each time this (?:model s )?unit ends a charge move each enemy unit within engagement range of (?:(?:that|this) unit|it) must take a battle shock test",
        re.IGNORECASE,
    )
    _CHARGE_END_ENGAGEMENT_SELECT_ONE_BATTLESHOCK_RE = re.compile(
        r"each time this (?:model s )?unit ends a charge move select one enemy unit within engagement range of (?:(?:that|this) unit|it) "
        r"that enemy unit must take a battle shock test subtracting (?P<penalty>\d+) from that test",
        re.IGNORECASE,
    )
    _START_ANY_PHASE_CLEAR_BATTLESHOCK_RE = re.compile(
        r"once per battle at the start of any phase you can select one friendly (?P<keyword>[a-z0-9 ]+?) unit that is battle shocked "
        r"and within (?P<range>\d+)\s*\"?\s*of (?:this model|the bearer|this unit s (?P<model>[a-z0-9 ]+?) model) that unit is no longer battle shocked",
        re.IGNORECASE,
    )
    _FIGHT_SELECTED_ENEMY_MELEE_HIT_PENALTY_RE = re.compile(
        r"each time an enemy unit(?: excluding (?P<exclude>titanic|titan) units?)? within engagement range of one or more units "
        r"with this ability is selected to fight until the end of the phase each time a model in that enemy unit makes "
        r"(?:a )?melee attack(?:s)? subtract 1 from the hit roll",
        re.IGNORECASE,
    )
    _NO_ADVANCE_START_OR_END_WITHIN_RE = re.compile(
        r"enemy models cannot start or end an advance move within (?P<range>\d+) of this model",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_END_ENGAGEMENT_MORTAL_EIGHT_D6_RE = re.compile(
        r"at the end of the fight phase you can select one enemy unit within engagement range of this model "
        r"and roll (?:eight|8) d6 for each 4 that enemy unit suffers 1 mortal wounds?",
        re.IGNORECASE,
    )
    _LEADING_WEAPON_ATTACKS_BONUS_RE = re.compile(
        r"while this model is leading a unit add (?P<bonus>\d+) to the attacks characteristic of "
        r"(?P<weapon>[a-z0-9 ]+?) weapons? equipped by models in that unit",
        re.IGNORECASE,
    )
    _FIGHT_SELECTED_MORTAL_TABLE_RE = re.compile(
        r"each time this model s unit is selected to fight you can select one enemy unit within engagement range of this model s unit "
        r"and roll one d6 on a 2 3 that enemy unit suffers 1 mortal wounds? on a 4 5 that enemy unit suffers d3 mortal wounds? "
        r"on a 6 that enemy unit suffers d3 3 mortal wounds?",
        re.IGNORECASE,
    )
    _DAEMONIC_PATRONS_RE = re.compile(
        r"each time this unit is selected to fight it can call upon (?:the )?daemonic patrons if it does until the end of the phase "
        r"each time a model in this unit makes an attack an unmodified wound roll of (?P<thresh>\d) scores a critical wound "
        r"at the end of the fight phase if this unit called upon (?:the )?daemonic patrons this phase and no enemy models were destroyed "
        r"by attacks made by models in this unit this phase one model in this unit is destroyed",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_ONCE_MELEE_AP_ATTACKS_RE = re.compile(
        r"once per battle at the start of the fight phase this model can use this ability if it does until the end of the phase "
        r"add 3 to the attacks characteristic of melee weapons equipped by this model and improve the armou?r penetration "
        r"characteristic of those weapons by 1",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_MELEE_ATTACKS_STRENGTH_RE = re.compile(
        r"once per battle at the start of the fight phase this model can use this ability if it does until the end of the phase "
        r"add (?P<attacks>\d+) to the attacks and strength characteristics of melee weapons equipped by this model",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_MELEE_ATTACKS_SET_INVULN_RE = re.compile(
        r"once per battle at the start of the fight phase this model can use this ability if it does until the end of the phase "
        r"this model has a (?P<invuln>\d)\+? invulnerable save and change the attacks characteristic of melee weapons "
        r"equipped by this model to (?P<attacks>\d+)",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_MELEE_FULL_BUFF_RE = re.compile(
        r"once per battle at the start of the fight phase this model can use this ability if it does until the end of the phase "
        r"improve the strength attacks armou?r penetration and damage characteristics of melee weapons equipped by this model by (?P<val>\d+)",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_HELLFORGED_ATTACKS_RE = re.compile(
        r"once per battle at the start of the fight phase this model can use this ability if it does until the end of the phase "
        r"add (?P<val>\d+) to the attacks characteristic of this model s hellforged weapons",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_TARGET_ATTACK_BONUS_RE = re.compile(
        r"at the start of the fight phase select one enemy unit within (?P<range>\d+)\s*\"?\s*of(?: and visible to)? this model "
        r"until the end of the phase each time a friendly (?P<keyword>[a-z0-9 ]+?) unit makes an attack that targets that unit "
        r"improve the strength armou?r penetration and damage characteristics of that attack by (?P<val>\d+)",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_TARGET_DAMAGE_BONUS_RE = re.compile(
        r"at the start of the fight phase you can select one enemy unit within (?P<range>\d+)\s*\"?\s*(?:of\s*)?(?:and visible to\s*)?this model "
        r"until the end of the phase each time an attack made by (?:a|an) (?P<keyword>[a-z0-9 ]+?) model is allocated to a model in that unit "
        r"add (?P<val>\d+) to the damage characteristic of that attack",
        re.IGNORECASE,
    )
    _RANGED_AFFLICTED_STRENGTH_AP_BONUS_RE = re.compile(
        r"if this unit has a starting strength of (?P<min>\d+) or more or if a character is leading this unit then each time a model in this unit makes "
        r"a ranged attack that targets an afflicted unit improve the strength and armou?r penetration characteristics of that attack by (?P<val>\d+)",
        re.IGNORECASE,
    )
    _SPORE_LACED_SHOCK_WAVES_RE = re.compile(
        r"in your shooting phase each time you select a target for this model s (?P<weapon>[a-z0-9 ]+) roll one d6 for the target unit and every other "
        r"enemy unit within (?P<range>\d+) of the target unit adding (?P<bonus>\d+) to that roll if the unit being rolled for is afflicted on a "
        r"(?P<threshold>\d)\+? the unit being rolled for is struck by spores after resolving all of this model s attacks against the target unit each unit "
        r"struck by spores suffers (?P<mw>d3|d6|\d+) mortal wounds?",
        re.IGNORECASE,
    )
    _THUNDERSHOCK_RE = re.compile(
        r"in your shooting phase each time you select a target for this model s (?P<weapon>[a-z0-9 ]+) roll one d6 for the target unit and one d6 for each other "
        r"enemy unit within (?P<range>\d+) of the target unit on a (?P<threshold>\d)\+? the unit being rolled for is struck by arcing energies after resolving all "
        r"of this model s attacks against the target unit each unit struck by arcing energies suffers (?P<mw>d3|d6|\d+) mortal wounds?",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_TARGET_MELEE_WOUND_BONUS_RE = re.compile(
        r"at the start of the fight phase select one enemy unit within (?P<range>\d+)\s*\"?\s*of this model "
        r"until the end of the phase each time a friendly (?P<keyword>[a-z0-9 ]+?) model makes a melee attack that targets that enemy unit "
        r"add (?P<bonus>\d+) to the wound roll",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_TARGET_MELEE_WOUND_PENALTY_RE = re.compile(
        r"each time a model in that enemy unit makes a melee attack subtract (?P<pen>\d+) from the wound roll",
        re.IGNORECASE,
    )
    _FIGHT_PHASE_DATA_SPIKE_RE = re.compile(
        r"at the start of the fight phase you can select one enemy vehicle unit within engagement range of this model s unit "
        r"and roll one d6 on a (?P<threshold>\d)\+? that enemy unit suffers (?P<mw>d3|d6|\d+) mortal wounds? "
        r"and until the end of the phase the weapon skill characteristic of melee weapons equipped by that enemy unit is worsened by (?P<pen>\d+)",
        re.IGNORECASE,
    )
    _HARBINGER_OF_DEATH_RE = re.compile(
        r"each time this model is selected to fight select one of the following abilities until the end of the phase this model s "
        r"hellforged weapons have that ability",
        re.IGNORECASE,
    )
    _MALIGN_SACRIFICE_RE = re.compile(
        r"at the start of the fight phase if this unit contains one or more (?P<model>[a-z0-9 ]+?) models "
        r"you can select one of those models and one enemy unit within engagement range of this unit then roll one d6 "
        r"on a 2 5 that enemy unit suffers 1 mortal wound on a 6 that enemy unit suffers d3 mortal wounds "
        r"that (?P=model) model is then destroyed",
        re.IGNORECASE,
    )
    _HYSTERICAL_FRENZY_RE = re.compile(
        r"once per fight phase just after an enemy unit selects a slaanesh legiones daemonica unit from your army as a target "
        r"one friendly psyker that is within (?P<range>\d+)\s*\"?\s*of that slaanesh unit and has this ability can use it "
        r"if it does until the end of the phase each time a model in that slaanesh unit is destroyed roll one d6 on a 4 "
        r"do not remove it from play that model can fight after the attacking model s unit has finished making its attacks and is then removed from play",
        re.IGNORECASE,
    )
    _HYSTERICAL_FRENZY_PASSIVE_RE = re.compile(
        r"each time a model in this model s unit is destroyed if that model has not fought this phase do not remove it from play "
        r"the destroyed model can fight after the attacking unit has finished making its attacks and is then removed from play",
        re.IGNORECASE,
    )
    _SACRIFICIAL_DAGGER_RE = re.compile(
        r"once per phase when this model is selected to shoot or fight it can use this ability if it does this model s unit suffers 1 mortal wound "
        r"and until the end of the phase each time this model makes a psychic attack add 1 to the hit roll and add 1 to the wound roll",
        re.IGNORECASE,
    )
    _SACRIFICIAL_BLESSING_RE = re.compile(
        r"while this model is leading a unit in your shooting phase and the fight phase each time that unit is selected to shoot or fight "
        r"this model can use this ability if it does select one bodyguard model in that unit that bodyguard model is destroyed and until the end of the phase "
        r"add d3 to the attacks and strength characteristics of psychic weapons equipped by this model",
        re.IGNORECASE,
    )
    _TWISTED_SORCERIES_RE = re.compile(
        r"once per battle in your shooting phase or the fight phase this model can use this ability if it does until the end of the phase "
        r"improve the strength and attacks characteristics of psychic weapons equipped by this model by (?P<val>\d+)",
        re.IGNORECASE,
    )
    _GIFT_OF_CHAOS_RE = re.compile(
        r"each time this model is selected to shoot or fight after resolving its attacks select one enemy unit hit by one or more of those attacks "
        r"that had the psychic ability that unit must take a leadership test if that test is failed that unit suffers d3 mortal wounds",
        re.IGNORECASE,
    )
    _START_ANY_PHASE_DAMAGE_SET_ONE_RE = re.compile(
        r"once per battle at the start of any phase this model can use this ability if it does until the end of the phase "
        r"each time an attack is allocated to this model change the damage characteristic of that attack to 1",
        re.IGNORECASE,
    )
    _START_ANY_PHASE_MODEL_INVULN_RE = re.compile(
        r"once per battle at the start of any phase this model can use this ability if it does until the end of the phase "
        r"this model has a (?P<invuln>\d+) invulnerable save",
        re.IGNORECASE,
    )
    _START_ANY_PHASE_MODEL_UNIT_INVULN_RE = re.compile(
        r"once per battle at the start of any phase this model can use this ability if it does until the end of the phase "
        r"all models in this model s unit have a (?P<invuln>\d+) invulnerable save",
        re.IGNORECASE,
    )
    _START_ANY_PHASE_UNIT_FNP_RE = re.compile(
        r"once per battle at the start of any phase this unit can use this ability if it does until the end of the phase "
        r"models in this unit have the feel no pain (?P<val>\d+)(?: ability)?",
        re.IGNORECASE,
    )
    _ONCE_PER_BATTLE_ADVANCE_AND_CHARGE_RE = re.compile(
        r"once per battle in your charge phase (?:this model s unit|this unit|this model) is eligible to declare a charge "
        r"in a turn (?:in )?which it advanced",
        re.IGNORECASE,
    )
    _MOVEMENT_PHASE_ONCE_NORMAL_MOVE_WEAPON_ATTACKS_RE = re.compile(
        r"once per battle (?:in|during) your movement phase "
        r"(?:(?:before this model makes (?:a )?normal move it can use this ability)|"
        r"(?:this model can use this ability before it makes (?:a )?normal move)) "
        r"if it does until the end of the turn add (?P<move>\d+d\d+|\d+) to this model s move characteristic "
        r"and add (?P<attacks>\d+) to the attacks characteristic of this model s (?P<weapon>[a-z0-9 ]+? weapon(?:s)?)",
        re.IGNORECASE,
    )
    _MOVEMENT_PHASE_NORMAL_MOVE_SPEED_MORTAL_WOUNDS_RE = re.compile(
        r"in your movement phase each time this unit is selected to make (?:a )?normal move it can use this ability "
        r"if it does until the end of the turn this unit is not eligible to declare a charge and models in it have a move characteristic of (?P<move>\d+) "
        r"each time this unit uses this ability at the end of the phase roll (?:one|1) d6 for each model in this unit for each 1 "
        r"this unit suffers 1 mortal wounds?",
        re.IGNORECASE,
    )
    _MOVEMENT_PHASE_END_VISIBLE_WOUND_BONUS_RE = re.compile(
        r"at the end of your movement phase select one enemy unit within (?P<range>\d+) of and visible to this model "
        r"until the start of your next command phase each time a friendly (?P<keyword>[a-z0-9 ]+) models? make(?:s)? an attack that targets that enemy unit "
        r"add (?P<bonus>\d+) to the wound rolls?(?: each unit can only be selected for this ability once per turn)?",
        re.IGNORECASE,
    )
    _MOVEMENT_PHASE_END_VISIBLE_HIT_BONUS_RE = re.compile(
        r"at the end of your movement phase select one enemy unit within (?P<range>\d+) of and visible to this model "
        r"until the start of your next command phase each time a friendly (?P<keyword>[a-z0-9 ]+) models? make(?:s)? an attack that targets that enemy unit "
        r"add (?P<bonus>\d+) to the hit rolls?(?: each unit can only be selected for this ability once per turn)?",
        re.IGNORECASE,
    )
    _BATTLE_FOCUS_TOKEN_REFUND_ON_AGILE_MANEUVER_RE = re.compile(
        r"while this model is leading a unit each time you spend a battle focus token to enable that unit to perform "
        r"an agile (?:manoeuvre|maneuver) roll (?:one|1) d6 on a (?P<threshold>\d)\+? you gain 1 battle focus token",
        re.IGNORECASE,
    )
    _LEADING_LEADERSHIP_REROLL_RE = re.compile(
        r"while this model is leading a unit you can re ?roll leadership tests taken for that unit",
        re.IGNORECASE,
    )
    _DARK_PACTS_LEADERSHIP_REROLL_RE = re.compile(
        r"each time the (?:bearer s|bearers) unit takes a leadership test for the dark pacts ability you can re ?roll that test",
        re.IGNORECASE,
    )
    _CREWED_PLATFORM_RE = re.compile(
        r"when the last (?P<crew>guardian defender|storm guardian) model in this unit is destroyed "
        r"any remaining (?P<platform>heavy weapon platform|serpent s scale platform|serpents scale platform) models in this unit are also destroyed",
        re.IGNORECASE,
    )
    _LEADING_UNMODIFIED_SIX_ROLL_RE = re.compile(
        r"while this model is leading a unit once per phase you can change the result of one hit roll one wound roll or one "
        r"damage roll made for a model in (?:that|this|the bearer s) unit(?: (?P<exclude>excluding support weapon models?))? "
        r"to an unmodified 6",
        re.IGNORECASE,
    )
    _MODEL_ONCE_PER_BATTLE_UNMODIFIED_SIX_RE = re.compile(
        r"once per battle after (?:making )?(?:a )?hit roll (?:a )?wound roll or (?:a )?"
        r"(?:saving throw|save roll)(?: is made| made)? for this model you can change the result of that roll to "
        r"(?:an unmodified |a )?6",
        re.IGNORECASE,
    )
    _MODEL_ONCE_PER_BATTLE_ROUND_UNMODIFIED_SIX_RE = re.compile(
        r"once (?:per|in each) (?:battle round|turn) after (?:making )?(?:a )?hit roll (?:a )?wound roll or (?:a )?"
        r"(?:saving throw|save roll)(?: is made| made)? for this model you can change the result of that roll to "
        r"(?:an unmodified |a )?6",
        re.IGNORECASE,
    )
    _MODEL_ONCE_PER_BATTLE_ALLOCATED_DAMAGE_ZERO_RE = re.compile(
        r"once per battle when an attack is allocated to (?:the bearer|this model) you (?:can )?change "
        r"(?:the )?damage characteristic(?: of that attack)? to 0",
        re.IGNORECASE,
    )
    _MODEL_ONCE_PER_BATTLE_ROUND_ALLOCATED_DAMAGE_ZERO_RE = re.compile(
        r"once per battle round when an attack is allocated to (?:the bearer|this model) you (?:can )?change "
        r"(?:the )?damage characteristic(?: of that attack)? to 0",
        re.IGNORECASE,
    )
    _MASTER_OF_STANCES_RE = re.compile(
        r"once per battle when this model s unit is selected to fight it can use this ability if it does until that fight is resolved "
        r"both ka tah stances are active for that unit instead of only one",
        re.IGNORECASE,
    )
    _MOMENT_SHACKLE_RE = re.compile(
        r"once per battle at the start of the fight phase you can select one of the following to take effect until the end of the phase "
        r"this model s (?P<weapon>[a-z0-9 ]+?) melee weapon has an attacks characteristic of (?P<attacks>\d+) "
        r"this model has a (?P<invuln>\d)\+? invulnerable save",
        re.IGNORECASE,
    )
    _START_OF_BATTLE_KEYWORD_REROLL_ONES_RE = re.compile(
        r"at the start of the battle select one of the following keywords (?P<keywords>[a-z0-9 ]+) "
        r"each time this model makes an attack(?:s)? that targets? a unit with the selected keyword "
        r"re ?roll a hit roll of 1 and re ?roll a wound roll of 1",
        re.IGNORECASE,
    )
    _MOVE_OVER_MORTAL_WOUNDS_RE = re.compile(
        r"(?:(?:in|during) your movement phase(?:,)?\s+)?(?:each time|after) (?:this model|the bearer) ends a (?P<moves>[a-z ]+) move "
        r"(?:you can )?(?:select|choose) one enemy unit(?: excluding monsters? and vehicles?(?: units)?)? "
        r"(?:that )?(?:it )?moved over during that move "
        r"(?:if you do )?(?:and |then )?roll (?P<dice>\d+|one|two|three|four|five|six|seven|eight|nine|ten) d6 "
        r"(?:adding (?P<fly_bonus>\d+) to each result if that enemy unit can fly )?"
        r"for each (?P<threshold>\d)\+ that (?:enemy )?unit suffers (?P<mw>d3|d6|\d+) mortal wounds?",
        re.IGNORECASE,
    )
    _UNIT_MOVE_OVER_MORTAL_WOUNDS_RE = re.compile(
        r"(?:once per battle(?:,)?\s+)?(?:(?:in|during) your movement phase(?:,)?\s+)?(?:each time|after) this unit ends a (?P<moves>[a-z ]+) move "
        r"(?:you can )?(?:select|choose) one enemy unit(?: excluding monsters? and vehicles?(?: units)?)? "
        r"(?:that )?(?:it )?moved over during that move "
        r"(?:if you do )?(?:and |then )?roll (?:\d+|one|two|three|four|five|six|seven|eight|nine|ten) d6 for each model in this unit "
        r"(?:adding (?P<fly_bonus>\d+) to each result if that enemy unit can fly )?"
        r"for each (?P<threshold>\d)\+? that (?:enemy )?unit suffers (?P<mw>d3|d6|\d+) mortal wounds?",
        re.IGNORECASE,
    )
    _MOVE_OVER_NO_COVER_RE = re.compile(
        r"each time this model ends a normal move select one enemy unit it moved over during that move "
        r"until the end of the turn models in that unit cannot have the benefit of cover",
        re.IGNORECASE,
    )
    _GRENADE_PACK_FLYOVER_RE = re.compile(
        r"once per turn in your movement phase when this unit is set up on the battlefield or ends a "
        r"normal advance or fall back move it can use this ability if it does select one enemy unit within "
        r"(?P<range>\d+) of and visible to this unit and roll one d6 for each (?P<models>[a-z0-9 ]+) model in this unit "
        r"for each (?P<threshold>\d)\+? that enemy unit suffers (?P<mw>\d+) mortal wounds? "
        r"\(?(?:to a maximum of )?(?P<cap>\d+)? mortal wounds?\)?",
        re.IGNORECASE,
    )
    _END_OF_FIGHT_EMBARK_RE = re.compile(
        r"at the end of the fight phase if there are no models currently embarked within this transport you can select one "
        r"friendly (?P<keyword>[a-z0-9 ]+) infantry unit that "
        r"(?:only includes models from the units listed in this unit s transport section )?"
        r"(?:that )?has (?P<max>\d+) or fewer models "
        r"(?:and )?that is wholly within (?P<range>\d+) of this transport "
        r"(?:you cannot select a unit that can fly )?"
        r"unless that unit is within engagement range of one or more enemy units it can embark within this transport",
        re.IGNORECASE,
    )
    _SWEEPING_ADVANCE_RE = re.compile(
        r"once per battle at the end of the fight phase if this model s unit has fought this phase "
        r"if it is within engagement range of one or more enemy units it can make a fall back move "
        r"(?:or )?if it is not within engagement range of one or more enemy units it can make a normal move",
        re.IGNORECASE,
    )
    _RAID_AND_RUN_RE = re.compile(
        r"at the end of the fight phase if this unit was eligible to fight this phase and is not within engagement range of one or more enemy units "
        r"it can make a normal move of up to d3 3 "
        r"otherwise if this unit was eligible to fight this phase this unit can make a fall back move of up to d3 3",
        re.IGNORECASE,
    )
    _TITANIC_AGILITY_RE = re.compile(
        r"each time this model makes a normal advance or fall back move it can move through models and terrain features "
        r"when doing so it can move within engagement range of enemy models but cannot end that move within engagement range of them",
        re.IGNORECASE,
    )
    _TITANIC_STRIDES_RE = re.compile(
        r"each time this model makes a normal advance or fall back move it can move through models excluding titanic models "
        r"and sections of terrain features that are (?P<height>\d+) or less in height when doing so it can move within engagement range of enemy models "
        r"but cannot end that move within engagement range of them it can also move through sections of terrain features that are more than (?P=height) "
        r"in height but if it does after it has moved roll one d6 on a 1 this model is battle shocked",
        re.IGNORECASE,
    )
    _EMPOWERED_BY_DEATH_RE = re.compile(
        r"at the start of the fight phase if this model\s*s unit is below its starting strength until the end of the phase models in that unit "
        r"have the fights first ability",
        re.IGNORECASE,
    )
    _EMPYRIC_AMBUSH_RE = re.compile(
        r"eligible to declare a charge in a turn in which it used its flickerjump ability",
        re.IGNORECASE,
    )
    _MOVE_OVER_MORTAL_WOUNDS_REROLL_RE = re.compile(
        r"each time you roll (?:a d6 for the bearer while resolving|to inflict wounds using) this unit s eviscerating fly by ability "
        r"you can re ?roll (?:the result|one d6(?: for each model in this unit equipped with cluster caltrops)?)",
        re.IGNORECASE,
    )
    _FIRST_FAILED_SAVE_DAMAGE_ZERO_RE = re.compile(
        r"once per turn the first time a saving throw is failed for (?:the bearer s unit|this unit|this model s unit|this models unit) "
        r"change the damage characteristic of that attack to 0",
        re.IGNORECASE,
    )
    _CRUEL_AMUSEMENT_RE = re.compile(
        r"in your shooting phase each time this model is selected to shoot select one of the abilities below "
        r"until the end of the phase this model s (?P<weapon>[a-z0-9 ]+) has that ability",
        re.IGNORECASE,
    )
    _MASTER_OF_MAGICKS_RE = re.compile(
        r"in your shooting phase select one of the following abilities ignores cover lethal hits sustained hits d3 "
        r"until the end of the phase this model s (?P<weapon>[a-z0-9 ]+) has that ability",
        re.IGNORECASE,
    )
    _CRY_OF_THE_WIND_RE = re.compile(
        r"each time this model is set up on the battlefield until the end of the turn "
        r"each time this model makes a ranged attack a successful unmodified hit roll scores a critical hit",
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
    _COMMAND_PHASE_END_LEADERSHIP_CP_GAIN_RE = re.compile(
        r"at the end of your command phase if "
        r"(?:this model|the bearer|the bearer s model|the bearers model) is on the battlefield "
        r"take a leadership test for (?:this model|the bearer|the bearer s model|the bearers model) "
        r"if that test is passed you gain (?P<cp>\d+|one)\s*(?:cp|command points?)",
        re.IGNORECASE,
    )
    _RETURN_ON_DEATH_RE = re.compile(
        r"the first time (?:(?:this model|the bearer) is destroyed|a model with this ability is destroyed in a battle round)"
        r"(?: remove it from play without resolving its deadly demise ability)?(?: then)? "
        r"(?:at the end of the phase roll one d6|roll one d6 at the end of the phase) on a (?P<roll>\d+) "
        r"set (?:this model|the bearer|that model) back up on the battlefield(?: as close as possible to where it was destroyed)? "
        r"and not within engagement range of (?:one or more|any) enemy (?:units|models)(?: with)? "
        r"(?P<wounds>its full wounds remaining|(?:d3|d6|\d+) wounds? remaining)",
        re.IGNORECASE,
    )
    _BLINDING_SPRAY_RE = re.compile(
        r"in the fight phase you can select one model from your army with this ability to use this ability "
        r"if you do until the end of the phase that model(?:\s+s|s)? unit has the fights first ability "
        r"each model can only be selected for this ability once per battle",
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
        r"for\s+each\s+4\+.*?(?P<mw>d3|1)\s+mortal\s+wounds?",
        re.IGNORECASE,
    )
    _CHARGE_END_MORTAL_REMAINING_WOUNDS_RE = re.compile(
        r"each\s+time\s+this\s+model\s+ends?\s+a\s+charge\s+move.*?"
        r"(?:select|choose)\s+one\s+enemy\s+unit\s+within\s+engagement\s+range\s+of\s+it.*?"
        r"roll\s+one\s+d6\s+for\s+each\s+of\s+this\s+model'?s\s+remaining\s+wounds.*?"
        r"for\s+each\s+4\+.*?suffers?\s+1\s+mortal\s+wounds?"
        r"(?:.*?maximum\s+of\s+6\s+mortal\s+wounds?)?",
        re.IGNORECASE,
    )
    _CHARGE_MOVE_DEVASTATING_WOUNDS_RE = re.compile(
        r"each\s+time\s+this\s+(?:model|unit|model'?s\s+unit)\s+makes?\s+a\s+charge\s+move.*?"
        r"until\s+the\s+end\s+of\s+(?:the\s+)?turn.*?"
        r"melee\s+weapons.*?devastating\s+wounds",
        re.IGNORECASE,
    )
    _CHARGE_END_WEAPON_KEYWORD_BONUS_RE = re.compile(
        r"(?:while\s+this\s+model\s+is\s+leading\s+a\s+unit\s+)?each\s+time\s+(?:this|that)\s+unit\s+ends?\s+a\s+charge\s+move\s+"
        r"until\s+the\s+end\s+of\s+the\s+turn\s+(?P<weapon>[a-z0-9 ]+?)\s+equipped\s+by\s+models\s+in\s+that\s+unit\s+"
        r"have\s+the\s+(?P<keyword>[a-z0-9 \-]+)\s+ability",
        re.IGNORECASE,
    )
    _CHARGE_END_MODEL_MELEE_STRENGTH_AP_BONUS_RE = re.compile(
        r"(?:while\s+this\s+model\s+is\s+leading\s+a\s+unit\s+)?"
        r"each\s+time\s+(?:this\s+model\s+s\s+unit|that\s+unit|this\s+unit)\s+ends?\s+a\s+charge\s+move\s+"
        r"until\s+the\s+end\s+of\s+the\s+turn\s+"
        r"add\s+(?P<strength>\d+)\s+to\s+the\s+strength\s+characteristic\s+of\s+melee\s+weapons\s+equipped\s+by\s+this\s+model\s+"
        r"and\s+improve\s+the\s+armou?r\s+penetration\s+characteristics?\s+of\s+those\s+weapons\s+by\s+(?P<ap>\d+)",
        re.IGNORECASE,
    )
    _CHARGE_MOVE_MODEL_WEAPON_PROFILE_ATTACKS_BONUS_RE = re.compile(
        r"each\s+time\s+this\s+model\s+makes?\s+a\s+charge\s+move\s+until\s+the\s+end\s+of\s+the\s+turn\s+"
        r"add\s+(?P<strike>\d+)\s+to\s+the\s+attacks\s+characteristic\s+of\s+(?:this\s+model\s+s|this\s+models|its)\s+"
        r"(?P<weapon1>[a-z0-9 ]+?)\s+strike\s+profile\s+and\s+add\s+(?P<sweep>\d+)\s+to\s+the\s+attacks\s+characteristic\s+of\s+"
        r"(?:this\s+model\s+s|this\s+models|its)\s+(?P<weapon2>[a-z0-9 ]+?)\s+sweep\s+profile",
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
    _CHARGE_END_MORTAL_TABLE_2_5_D3_RE = re.compile(
        r"each\s+time\s+this\s+model\s+ends?\s+a\s+charge\s+move.*?"
        r"(?:you\s+can\s+)?(?:select|choose)\s+one\s+enemy\s+unit\s+within\s+engagement\s+range\s+of\s+(?:this\s+model|it)\s+"
        r"and\s+roll\s+one\s+d6.*?on\s+a\s+2\s*-\s*5.*?suffers?\s+d3\s+mortal\s+wounds?.*?"
        r"on\s+a\s+6.*?suffers?\s+d3\s*\+\s*3\s+mortal\s+wounds?",
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
    _DAEMONIC_ALLEGIANCE_KEYWORD_ONLY_TOKENS = (
        "select",
        "one",
        "of",
        "the",
        "keywords",
    )
    _DAEMONIC_ALLEGIANCE_WEAPON_BONUS_RE = re.compile(
        r"if this model has the (?P<keyword>khorne|tzeentch|nurgle|slaanesh) keyword, "
        r"add (?P<value>\d+) to the (?P<char>strength|attacks) characteristic of this model'?s "
        r"(?P<weapon>[a-z0-9 '\\-]+?)(?:\.|$)",
        re.IGNORECASE,
    )
    _DAEMONIC_ALLEGIANCE_TOUGHNESS_BONUS_RE = re.compile(
        r"if this model has the (?P<keyword>khorne|tzeentch|nurgle|slaanesh) keyword, "
        r"add (?P<value>\d+) to this model'?s toughness characteristic",
        re.IGNORECASE,
    )
    _DAEMONIC_ALLEGIANCE_MOVE_BONUS_RE = re.compile(
        r"if this model has the (?P<keyword>khorne|tzeentch|nurgle|slaanesh) keyword, "
        r"add (?P<value>\d+)\"? to this model'?s move characteristic",
        re.IGNORECASE,
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
    _BEARER_INVULNERABLE_SAVE_WITH_ALLOCATED_DAMAGE_RE = re.compile(
        r"^the bearer has a (\d)\+ invulnerable save\s+and\s+each\s+time\s+an\s+attack\s+"
        r"is\s+allocated\s+to\s+the\s+bearer,\s*subtract\s+\d+\s+from\s+the\s+damage\s+"
        r"characteristic\s+of\s+that\s+attack\.?$",
        re.IGNORECASE,
    )
    _BEARER_ALLOCATED_DAMAGE_REDUCTION_RE = re.compile(
        r"each\s+time\s+(?:an|a)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+is\s+allocated\s+"
        r"to\s+the\s+bearer,\s*subtract\s+(?P<val>\d+)\s+from\s+the\s+damage\s+"
        r"characteristic\s+of\s+that\s+attack",
        re.IGNORECASE,
    )
    _BEARER_ALLOCATED_DAMAGE_HALVING_RE = re.compile(
        r"each\s+time\s+(?:an|a)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+is\s+allocated\s+"
        r"to\s+the\s+bearer,\s*(?:halve|half)\s+the\s+damage\s+characteristic\s+"
        r"of\s+that\s+attack",
        re.IGNORECASE,
    )
    _BEARER_ALLOCATED_DAMAGE_HALVING_ALT_RE = re.compile(
        r"each\s+time\s+(?:an|a)\s+(?:(?P<atype>melee|ranged)\s+)?attack\s+is\s+allocated\s+"
        r"to\s+the\s+bearer.*?damage\s+characteristic\s+of\s+that\s+attack\s+is\s+halved",
        re.IGNORECASE,
    )
    _BEARER_SAVE_CHARACTERISTIC_RE = re.compile(
        r"^the bearer has a save characteristic of (\d)\+\.?$",
        re.IGNORECASE,
    )
    _FORTIFICATION_COVER_RE = re.compile(
        r"^each time a ranged attack is allocated to a model if that model is not fully visible to "
        r"(?:every model in )?the attacking unit because of this fortification that model has the benefit of cover against that attack\.?$",
        re.IGNORECASE,
    )
    _SELFLESS_PROTECTOR_RE = re.compile(
        r"^each time a ranged attack is allocated to an imperial knights model from your army if that model is not fully visible to "
        r"(?:every model in )?the attacking unit because of this knight defender model that model has the benefit of cover and a 4 invulnerable save against that attack\.?$",
        re.IGNORECASE,
    )
    _TARGET_HIT_ROLL_PENALTY_UNIT_RE = re.compile(
        r"^each time (?:a model makes (?:a|an) )?(?:(?P<atype>melee|ranged) )?attack(?:s)?(?: that)? "
        r"(?:targets|is made against) this unit, subtract 1 (?:from|form) the hit roll",
        re.IGNORECASE,
    )
    _TARGET_HIT_ROLL_PENALTY_MODEL_RE = re.compile(
        r"^each time (?:a model makes (?:a|an) )?(?:(?P<atype>melee|ranged) )?attack(?:s)?(?: that)? "
        r"(?:targets|is made against) this model, subtract 1 (?:from|form) the hit roll",
        re.IGNORECASE,
    )
    _ENEMY_MELEE_HAZARDOUS_WHILE_TARGETING_RE = re.compile(
        r"melee weapons equipped by enemy models have the hazardous ability while targeting this (?:models unit|unit)",
        re.IGNORECASE,
    )
    _SPAWN_ONLY_ABILITY_RE = re.compile(r"^using\s+sir\s+hekhtur$", re.IGNORECASE)


for _mixin_module in _UNIT_MIXIN_MODULES:
    _mixin_module.Unit = Unit

