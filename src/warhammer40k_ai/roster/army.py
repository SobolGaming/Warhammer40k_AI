from typing import Any, Tuple, Dict, Set, List, Optional
from ..units.unit import Unit
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.waha_helper import WahaHelper
from warhammer40k_ai.utility.ability_support import (
    ABILITY_DISPARATE_PATHS,
    ABILITY_CORSAIRS_AND_TRAVELLING_PLAYERS,
    army_has_ability_id,
    pact_restrictions_for_faction,
)
from warhammer40k_ai.utility.entity_ids import get_entity_id
import re
import unicodedata
import uuid
import logging
logger = logging.getLogger(__name__)


# Define custom exception for validation errors
class ArmyValidationError(Exception):
    pass


SPACE_MARINE_CHAPTER_KEYWORDS = {
    "BLACK TEMPLARS",
    "BLOOD ANGELS",
    "DARK ANGELS",
    "DEATHWATCH",
    "IMPERIAL FISTS",
    "IRON HANDS",
    "RAVEN GUARD",
    "SALAMANDERS",
    "SPACE MARINES",
    "SPACE WOLVES",
    "ULTRAMARINES",
    "WHITE SCARS",
}
SPACE_MARINE_DEFAULT_CHAPTER = "SPACE MARINES"
SPACE_MARINE_EXPLICIT_CHAPTERS = SPACE_MARINE_CHAPTER_KEYWORDS - {SPACE_MARINE_DEFAULT_CHAPTER}
SPACE_MARINE_ALLOWED_NON_CHAPTER_FACTION_KEYWORDS: set[str] = {
    "AGENTS OF THE IMPERIUM",
}


def _normalize_faction_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name or ""))
    text = text.replace("'", "").replace("\u2019", "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


_SPACE_MARINE_CHAPTERS_NORMALIZED = {
    _normalize_faction_name(ch) for ch in SPACE_MARINE_EXPLICIT_CHAPTERS
}
_FACTION_NAME_ALIASES = {
    _normalize_faction_name("Adeptus Astartes"): "SM",
    _normalize_faction_name("Asuryani"): "AE",
    _normalize_faction_name("Legiones Daemonica"): "CD",
    _normalize_faction_name("Heretic Astartes"): "CSM",
    _normalize_faction_name("Agents of the Imperium"): "AOI",
}

SUPPORTED_FACTION_IDS = {
    "AC",
    "AE",
    "AM",
    "AS",
    "ADM",
    "AOI",
    "CD",
    "CSM",
    "DG",
    "DRU",
    "EC",
    "GC",
    "GK",
    "LOV",
    "NEC",
    "ORK",
    "QI",
    "QT",
    "SM",
    "TAU",
    "TS",
    "TYR",
    "WE",
}

SUPPORTED_FACTION_NAMES = [
    "Adepta Sororitas",
    "Adeptus Custodes",
    "Adeptus Mechanicus",
    "Aeldari",
    "Astra Militarum",
    "Chaos Daemons",
    "Chaos Knights",
    "Chaos Space Marines",
    "Death Guard",
    "Drukhari",
    "Emperor's Children",
    "Genestealer Cult",
    "Grey Knights",
    "Imperial Agents",
    "Imperial Knights",
    "Leagues of Votann",
    "Necrons",
    "Orks",
    "Space Marines",
    "Thousand Sons",
    "Tyranids",
    "T'au Empire",
    "World Eaters",
]


def _format_supported_factions() -> str:
    return ", ".join(SUPPORTED_FACTION_NAMES)


def _format_space_marine_chapters() -> str:
    chapters = sorted(ch.title() for ch in SPACE_MARINE_EXPLICIT_CHAPTERS)
    return ", ".join(chapters)


def _assert_supported_faction(faction_name: str, faction_id: Optional[str]) -> None:
    fid = str(faction_id or "").strip().upper()
    if fid:
        if fid not in SUPPORTED_FACTION_IDS:
            raise ArmyValidationError(
                f"Unsupported army faction '{faction_name}'. Supported factions: "
                f"{_format_supported_factions()}. Space Marines also allow chapters: "
                f"{_format_space_marine_chapters()}."
            )
        return
    raise ArmyValidationError(
        f"Unsupported army faction '{faction_name}'. Supported factions: "
        f"{_format_supported_factions()}. Space Marines also allow chapters: "
        f"{_format_space_marine_chapters()}."
    )

BLACK_TEMPLARS_FORBIDDEN_UNITS = {
    "GLADIATOR LANCER",
    "GLADIATOR REAPER",
    "GLADIATOR VALIANT",
    "IMPULSOR",
    "LAND RAIDER CRUSADER",
    "REPULSOR",
    "REPULSOR EXECUTIONER",
    "STERNGUARD VETERAN SQUAD",
}
DEATHWATCH_FORBIDDEN_UNITS = {
    "ASSAULT SQUAD",
    "ASSAULT SQUAD WITH JUMP PACKS",
    "ATTACK BIKE SQUAD",
    "DEVASTATOR SQUAD",
    "LAND SPEEDER STORM",
    "RELIC TERMINATOR SQUAD",
    "SCOUT BIKE SQUAD",
    "SCOUT SQUAD",
    "SCOUT SNIPER SQUAD",
    "TACTICAL SQUAD",
    "TERMINATOR ASSAULT SQUAD",
    "TERMINATOR SQUAD",
}
SPACE_WOLVES_FORBIDDEN_UNITS = {
    "APOTHECARY",
    "DEVASTATOR SQUAD",
    "TACTICAL SQUAD",
}
CULT_OF_DARK_GODS_UNITS = {
    "KHORNE BERZERKERS",
    "RUBRIC MARINES",
    "PLAGUE MARINES",
    "NOISE MARINES",
}
_AETHON_SHAAN_DATASHEET_ID = "000004148"
_KAYVAAN_SHRIKE_DATASHEET_ID = "000002708"
_CHAPTER_MASTER_OF_THE_RAVEN_GUARD_MARKER = (
    "loses its lone operative ability and it replaces its chapter master keyword with captain"
)
_COMPANY_HEROES_MUSTERING_MARKER = "must attach one captain or chapter master model to this unit"


def get_faction_id_from_name(faction_name: str) -> Optional[str]:
    """
    Map faction names from army list files to faction IDs used in datasheets.
    This mapping helps ensure the correct faction-specific datasheet is loaded.
    """
    import json
    import os
    
    # Normalize faction name for comparison
    faction_name_norm = _normalize_faction_name(faction_name)
    if not faction_name_norm:
        return None
    if faction_name_norm in _SPACE_MARINE_CHAPTERS_NORMALIZED:
        return "SM"
    alias_id = _FACTION_NAME_ALIASES.get(faction_name_norm)
    if alias_id:
        return alias_id
    
    # Load factions from the JSON file
    factions_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'wahapedia_data', 'Factions.json')
    with open(factions_file, 'r', encoding='utf-8') as f:
        factions = json.load(f)
    
    # Try exact match first
    for faction in factions:
        if _normalize_faction_name(faction.get("name", "")) == faction_name_norm:
            return faction.get("id")
    
    # Try partial matches for more flexible matching
    for faction in factions:
        faction_name_json = _normalize_faction_name(faction.get("name", ""))
        if faction_name_json and (
            faction_name_json in faction_name_norm
            or faction_name_norm in faction_name_json
        ):
            return faction.get("id")
    
    # If no match found, return None (will use generic lookup)
    return None


def _normalize_ability_text_for_rules(value: str) -> str:
    normalized = re.sub(r"<[^>]+>", " ", str(value or ""))
    normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _iter_unit_ability_entries_for_rules(unit) -> list[tuple[str, str]]:
    iter_entries = getattr(unit, "_iter_ability_entries_for_rules", None)
    if callable(iter_entries):
        entries: list[tuple[str, str]] = []
        for entry in iter_entries(model=None):
            if not isinstance(entry, tuple) or len(entry) < 2:
                continue
            entries.append((str(entry[0] or ""), str(entry[1] or "")))
        return entries

    entries: list[tuple[str, str]] = []
    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if isinstance(ability, str):
            entries.append((ability, ability))
            continue
        if isinstance(ability, dict):
            entries.append(
                (
                    str(ability.get("name") or ""),
                    str(ability.get("description") or ""),
                )
            )
            continue
        entries.append(
            (
                str(getattr(ability, "name", "") or ""),
                str(getattr(ability, "description", "") or ""),
            )
        )
    return entries


def _unit_has_named_ability_for_rules(unit, ability_name: str) -> bool:
    target = _normalize_ability_text_for_rules(ability_name)
    if not target:
        return False
    for name, _desc in _iter_unit_ability_entries_for_rules(unit):
        if _normalize_ability_text_for_rules(name) == target:
            return True
    return False


class Army:
    def __init__(self, faction: str, points_limit: int = 2000):
        self._id = str(uuid.uuid4())
        self.faction = faction
        # faction_id from Factions.json if known; parse_army_list can override later.
        self.faction_id: Optional[str] = get_faction_id_from_name(faction)
        self.faction_keyword = []
        self.points_limit = points_limit
        self.units = []
        self.warlord = None
        self.enhancements = []  # List of Enhancements used in the army
        self.detachment_rules = {}  # Placeholder for detachment-specific rules
        self.player = None  # Reference to the owning player
        self.tally_of_pestilence = 0
        self._has_tally_of_pestilence: Optional[bool] = None
        self.army_blueprint = None
        self.validated_muster = None
        self.detachments = []
        self.build_detachments = []
        self.build_unit_entries = []
        self.build_enhancement_assignments = []
        self.build_attachment_bindings = []
        self.attachment_bindings = []
        self.detachment_points_budget = None
        self.detachment_points_spent = 0
        self.detachment_points_summary = {}
        self.force_disposition = None
        self.allowed_force_dispositions = []
        self.build_metadata = {}


        self._rule_managers_configured = False
        self._reset_rule_managers()
        if self.faction_id:
            self.configure_rule_managers(force=True)

    @classmethod
    def with_detachment(
        cls,
        faction: str,
        detachment_type: str,
        points_limit: int = 2000,
    ) -> "Army":
        army = cls(faction=faction, points_limit=points_limit)
        army._seed_initial_detachment(detachment_type)
        if army.faction_id:
            army.configure_rule_managers(force=True)
        return army

    @property
    def id(self) -> str:
        return self._id

    @property
    def detachment_type(self) -> str:
        return self.get_primary_detachment_type()

    def __setattr__(self, name, value):
        previous_faction_id = None
        if name == "faction_id" and hasattr(self, "faction_id"):
            previous_faction_id = getattr(self, "faction_id", None)
        object.__setattr__(self, name, value)
        if name == "faction_id" and hasattr(self, "_rule_managers_configured"):
            self._sync_detachment_faction_ids(previous_faction_id=previous_faction_id)
            self.configure_rule_managers(force=True)

    def _normalize_detachment_seed(self, value: object) -> str:
        return str(value or "").strip()

    def _normalized_build_detachments(self) -> list:
        from .army_build import DetachmentSelection

        detachments = list(getattr(self, "build_detachments", []) or [])
        normalized = [
            detachment
            if isinstance(detachment, DetachmentSelection)
            else DetachmentSelection.from_dict(detachment)
            for detachment in detachments
        ]
        self.build_detachments = normalized
        return normalized

    def _seed_initial_detachment(self, value: object) -> None:
        from .army_build import DetachmentSelection
        from .army_runtime import DetachmentInstance

        detachment_type = self._normalize_detachment_seed(value)
        faction_id = str(getattr(self, "faction_id", "") or "").strip().upper() or "UNKNOWN"
        if not detachment_type:
            return

        detachment_points_cost = int(getattr(self, "detachment_points_spent", 0) or 0)
        selection = DetachmentSelection(
            selection_id="detachment_1",
            detachment_type=detachment_type,
            detachment_points_cost=detachment_points_cost,
            metadata={"source": "army.__init__"},
        )
        self.build_detachments = [selection]
        self.detachments = [
            DetachmentInstance(
                instance_id="detachment_instance_1",
                selection_id=selection.selection_id,
                faction_id=faction_id,
                detachment_type=selection.detachment_type,
                detachment_points_cost=detachment_points_cost,
                metadata={"source": "army.__init__"},
            )
        ]

    def _sync_detachment_faction_ids(self, *, previous_faction_id: object = None) -> None:
        target_faction_id = str(getattr(self, "faction_id", "") or "").strip().upper()
        if not target_faction_id:
            return
        prior_faction_id = str(previous_faction_id or "").strip().upper()
        detachments = self.get_detachment_instances()
        updated = False
        for detachment in detachments:
            current_faction_id = str(getattr(detachment, "faction_id", "") or "").strip().upper()
            if current_faction_id in {"", "UNKNOWN"} or (
                prior_faction_id and current_faction_id == prior_faction_id
            ):
                detachment.faction_id = target_faction_id
                updated = True
        if updated:
            self.detachments = detachments

    def _reset_rule_managers(self) -> None:
        self.blessings_of_khorne = None
        self.battle_focus = None
        self.templar_vows = None
        self.oath_of_moment = None
        self.combat_doctrines = None
        self.nurgles_gift = None
        self.shadow_of_chaos = None
        self.shadow_form = None
        self.wrathful_presence = None
        self.harbingers_of_dread = None
        self.code_chivalric = None
        self.bondsman = None
        self.cabal_of_sorcerers = None
        self.crimson_king = None
        self.synapse = None
        self.shadow_in_the_warp = None
        self.power_from_pain = None
        self.for_the_greater_good = None
        self.waaagh = None
        self.prioritised_efficiency = None
        self.cult_ambush = None
        self.acts_of_faith = None
        self.relics_of_the_matriarchs = None
        self.primarch_of_the_first_legion = None
        self.author_of_the_codex = None
        self.doctrina_imperatives = None
        self.voice_of_command = None
        self.voice_of_triarch = None
        self.gate_of_infinity = None
        self.daemon_primarch_slaanesh = None
        self.csm_warmaster = None
        self.emperors_children = None
        self.emperors_children_detachments = None
        self.deathstrike = None
        self.detachment_managers = {}
        from ..rules.detachment_registry import DETACHMENT_MANAGER_CLASSES
        for attr_name in DETACHMENT_MANAGER_CLASSES:
            setattr(self, attr_name, None)

    def configure_rule_managers(self, *, force: bool = False) -> None:
        if not force and getattr(self, "_rule_managers_configured", False):
            return
        self._reset_rule_managers()
        fid = str(getattr(self, "faction_id", "") or "").strip().upper()
        if not fid:
            self._rule_managers_configured = False
            return
        self._rule_managers_configured = True

        if fid == "WE":
            from ..rules.blessings_of_khorne import BlessingsOfKhorneManager
            from ..rules.wrathful_presence import WrathfulPresenceManager
            self.blessings_of_khorne = BlessingsOfKhorneManager()
            self.wrathful_presence = WrathfulPresenceManager(self)

        if fid == "AE":
            from ..rules.battle_focus import BattleFocusManager
            self.battle_focus = BattleFocusManager(self)

        if fid == "SM":
            from ..rules.templar_vows import TemplarVowsManager
            from ..rules.oath_of_moment import OathOfMomentManager
            from ..rules.combat_doctrines import CombatDoctrinesManager
            from ..rules.space_marines_author_of_the_codex import AuthorOfTheCodexManager
            from ..rules.space_marines_primarch_of_the_first_legion import PrimarchOfTheFirstLegionManager
            self.templar_vows = TemplarVowsManager(self)
            self.oath_of_moment = OathOfMomentManager(self)
            self.combat_doctrines = CombatDoctrinesManager(self)
            self.author_of_the_codex = AuthorOfTheCodexManager(self)
            self.primarch_of_the_first_legion = PrimarchOfTheFirstLegionManager(self)

        if fid == "DG":
            from ..rules.nurgles_gift import NurglesGiftManager
            self.nurgles_gift = NurglesGiftManager(self)

        if fid == "CD":
            from ..rules.shadow_of_chaos import ShadowOfChaosManager
            from ..rules.shadow_form import ShadowFormManager
            self.shadow_of_chaos = ShadowOfChaosManager(self)
            self.shadow_form = ShadowFormManager(self)

        if fid == "QT":
            from ..rules.harbingers_of_dread import HarbingersOfDreadManager
            self.harbingers_of_dread = HarbingersOfDreadManager(self)

        if fid == "QI":
            from ..rules.code_chivalric import CodeChivalricManager
            from ..rules.bondsman import BondsmanManager
            self.code_chivalric = CodeChivalricManager(self)
            self.bondsman = BondsmanManager(self)

        if fid == "TS":
            from ..rules.cabal_of_sorcerers import CabalOfSorcerersManager
            from ..rules.thousand_sons_crimson_king import CrimsonKingManager
            self.cabal_of_sorcerers = CabalOfSorcerersManager(self)
            self.crimson_king = CrimsonKingManager(self)

        if fid == "TYR":
            from ..rules.synapse import SynapseManager
            from ..rules.shadow_in_the_warp import ShadowInTheWarpManager
            self.synapse = SynapseManager(self)
            self.shadow_in_the_warp = ShadowInTheWarpManager(self)

        if fid == "DRU":
            from ..rules.power_from_pain import PowerFromPainManager
            self.power_from_pain = PowerFromPainManager(self)

        if fid == "TAU":
            from ..rules.for_the_greater_good import ForTheGreaterGoodManager
            self.for_the_greater_good = ForTheGreaterGoodManager(self)

        if fid == "NEC":
            from ..rules.necrons_voice_of_triarch import VoiceOfTriarchManager
            self.voice_of_triarch = VoiceOfTriarchManager(self)

        if fid == "ORK":
            from ..rules.waaagh import WaaaghManager
            self.waaagh = WaaaghManager(self)

        if fid == "LOV":
            from ..rules.prioritised_efficiency import PrioritisedEfficiencyManager
            self.prioritised_efficiency = PrioritisedEfficiencyManager(self)

        if fid == "GC":
            from ..rules.cult_ambush import CultAmbushManager
            self.cult_ambush = CultAmbushManager(self)

        if fid == "AS":
            from ..rules.acts_of_faith import ActsOfFaithManager
            from ..rules.adepta_sororitas_relics_of_the_matriarchs import RelicsOfTheMatriarchsManager
            self.acts_of_faith = ActsOfFaithManager(self)
            self.relics_of_the_matriarchs = RelicsOfTheMatriarchsManager(self)

        if fid == "ADM":
            from ..rules.doctrina_imperatives import DoctrinaImperativesManager
            self.doctrina_imperatives = DoctrinaImperativesManager(self)

        if fid in {"AM", "GC"}:
            from ..rules.voice_of_command import VoiceOfCommandManager
            self.voice_of_command = VoiceOfCommandManager(self)

        if fid == "AM":
            from ..rules.deathstrike import DeathstrikeManager
            self.deathstrike = DeathstrikeManager(self)

        if fid == "GC":
            # Genestealer Cults can also use Deathstrike
            from ..rules.deathstrike import DeathstrikeManager
            self.deathstrike = DeathstrikeManager(self)

        if fid == "GK":
            from ..rules.gate_of_infinity import GateOfInfinityManager
            self.gate_of_infinity = GateOfInfinityManager(self)

        if fid == "CSM":
            from ..rules.csm_warmaster import WarmasterManager
            self.csm_warmaster = WarmasterManager(self)

        from ..rules.detachment_registry import (
            DETACHMENT_MANAGER_BY_FACTION_ID,
            DETACHMENT_MANAGER_CLASSES,
        )
        attr_name = DETACHMENT_MANAGER_BY_FACTION_ID.get(fid)
        if attr_name:
            manager_cls = DETACHMENT_MANAGER_CLASSES.get(attr_name)
            if manager_cls is None:
                raise RuntimeError(f"Detachment manager class not registered for {attr_name}.")
            mgr = manager_cls(self)
            setattr(self, attr_name, mgr)
            self.detachment_managers[attr_name] = mgr

        if fid == "EC":
            from ..rules.emperors_children import EmperorsChildrenDetachmentManager
            from ..rules.daemon_primarch_slaanesh import DaemonPrimarchSlaaneshManager
            self.emperors_children = EmperorsChildrenDetachmentManager(self)
            self.daemon_primarch_slaanesh = DaemonPrimarchSlaaneshManager(self)
            self.emperors_children_detachments = self.emperors_children
            self.detachment_managers["emperors_children_detachments"] = self.emperors_children_detachments

    def get_detachment_manager_for_faction(self, faction_id: str):
        from ..rules.detachment_registry import get_detachment_manager_attr_for_faction
        fid = str(faction_id or "").strip().upper()
        if not fid:
            return None
        attr = get_detachment_manager_attr_for_faction(fid)
        if not attr:
            return None
        return getattr(self, attr, None)

    def get_detachment_manager_for_detachment_instance(self, detachment_instance):
        if detachment_instance is None:
            return None
        faction_id = str(
            getattr(detachment_instance, "faction_id", "") or getattr(self, "faction_id", "")
        ).strip().upper()
        return self.get_detachment_manager_for_faction(faction_id)

    def _normalize_detachment_name(self, value: object) -> str:
        text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())
        return re.sub(r"\s+", " ", text).strip()

    def get_detachment_instances(self) -> list:
        detachments = list(getattr(self, "detachments", []) or [])
        from .army_runtime import DetachmentInstance

        normalized = [
            detachment
            if isinstance(detachment, DetachmentInstance)
            else DetachmentInstance.from_dict(detachment)
            for detachment in detachments
        ]
        self.detachments = normalized
        return normalized

    def get_detachment_instances_for_faction(self, faction_id: str | None = None) -> list:
        target = str(faction_id or getattr(self, "faction_id", "") or "").strip().upper()
        detachments = list(self.get_detachment_instances() or [])
        if not target:
            return detachments
        return [
            detachment
            for detachment in detachments
            if str(getattr(detachment, "faction_id", "") or "").strip().upper() in {"", target}
        ]

    def get_detachment_types(self, faction_id: str | None = None) -> list[str]:
        names: list[str] = []
        for detachment in self.get_detachment_instances_for_faction(faction_id):
            name = str(getattr(detachment, "detachment_type", "") or "").strip()
            if name and name not in names:
                names.append(name)
        return names

    def get_primary_detachment_instance(self, faction_id: str | None = None):
        detachments = self.get_detachment_instances_for_faction(faction_id)
        if detachments:
            return detachments[0]
        return None

    def get_primary_detachment_type(self, faction_id: str | None = None) -> str:
        detachment = self.get_primary_detachment_instance(faction_id)
        if detachment is not None:
            return str(getattr(detachment, "detachment_type", "") or "")
        build_detachments = self._normalized_build_detachments()
        if build_detachments:
            return str(getattr(build_detachments[0], "detachment_type", "") or "")
        return ""

    def has_detachment_type(self, *names: str, faction_id: str | None = None) -> bool:
        detachment_names = [
            self._normalize_detachment_name(name)
            for name in self.get_detachment_types(faction_id)
            if self._normalize_detachment_name(name)
        ]
        if not detachment_names:
            return False
        for name in names:
            target = self._normalize_detachment_name(name)
            if not target:
                continue
            for det in detachment_names:
                if det == target:
                    return True
                if det.endswith("s") and det[:-1] == target:
                    return True
                if target.endswith("s") and target[:-1] == det:
                    return True
                if det in target or target in det:
                    return True
        return False

    def add_unit(self, unit: Unit) -> bool:
        if not self.faction_keyword:
            self.faction_keyword = unit.faction_keywords
        # TODO - fix once support for things like World Eaters Daemonkin Detachment is added
        #elif unit.faction_keywords != self.faction_keyword:
        #    raise ArmyValidationError(f"Unit {unit.name} does not match army faction {self.faction}.")
        unit.set_parent_army(self)
        apply_fn = getattr(unit, "apply_daemonic_allegiance_selection", None)
        if callable(apply_fn):
            apply_fn()
        self.units.append(unit)
        self._has_tally_of_pestilence = None
        we_mgr = getattr(self, "world_eaters_detachments", None)
        apply_fn = getattr(we_mgr, "apply_cult_of_blood_battleline_keywords", None) if we_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        dg_mgr = getattr(self, "death_guard_detachments", None)
        apply_fn = (
            getattr(dg_mgr, "apply_shamblerot_vectorium_poxwalkers_battleline_keywords", None)
            if dg_mgr is not None
            else None
        )
        if callable(apply_fn):
            apply_fn(unit)
        orks_mgr = getattr(self, "orks_detachments", None)
        apply_fn = getattr(orks_mgr, "apply_dread_mob_gretchin_battleline_keywords", None) if orks_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        apply_fn = getattr(orks_mgr, "apply_taktikal_brigade_stormboyz_battleline_keywords", None) if orks_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        cd_mgr = getattr(self, "chaos_daemons_detachments", None)
        apply_fn = getattr(cd_mgr, "apply_shadow_legion_keywords", None) if cd_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        csm_mgr = getattr(self, "chaos_space_marines_detachments", None)
        apply_fn = (
            getattr(csm_mgr, "apply_chaos_cult_traitor_guardsmen_battleline_keywords", None)
            if csm_mgr is not None
            else None
        )
        if callable(apply_fn):
            apply_fn(unit)
        apply_fn = getattr(csm_mgr, "apply_cult_of_the_arkifane_keywords", None) if csm_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        ae_mgr = getattr(self, "aeldari_detachments", None)
        apply_fn = getattr(ae_mgr, "apply_acrobatic_onslaught_travelling_players", None) if ae_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        ck_mgr = getattr(self, "chaos_knights_detachments", None)
        apply_fn = getattr(ck_mgr, "apply_houndpack_lance_battleline_keywords", None) if ck_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        ik_mgr = getattr(self, "imperial_knights_detachments", None)
        apply_fn = getattr(ik_mgr, "apply_spearhead_at_arms_battleline_keywords", None) if ik_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        apply_fn = getattr(ae_mgr, "apply_ride_the_wind_battleline_keywords", None) if ae_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        apply_fn = getattr(ae_mgr, "apply_spirit_conclave_battleline_keywords", None) if ae_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        ia_mgr = getattr(self, "imperial_agents_detachments", None)
        apply_fn = getattr(ia_mgr, "apply_extremis_sanction_extra_uses", None) if ia_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        sm_mgr = getattr(self, "space_marines_detachments", None)
        apply_fn = getattr(sm_mgr, "apply_company_of_hunters_battleline_keywords", None) if sm_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        apply_fn = getattr(sm_mgr, "apply_the_lost_brethren_battleline_keywords", None) if sm_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        tau_mgr = getattr(self, "tau_empire_detachments", None)
        apply_fn = getattr(tau_mgr, "apply_kroot_hunting_pack_battleline_keywords", None) if tau_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        lov_mgr = getattr(self, "leagues_of_votann_detachments", None)
        apply_fn = getattr(lov_mgr, "apply_delve_assault_shift_battleline_keywords", None) if lov_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        tyr_mgr = getattr(self, "tyranids_detachments", None)
        apply_fn = getattr(tyr_mgr, "apply_subterranean_assault_burrower_keywords", None) if tyr_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        apply_fn = getattr(tyr_mgr, "apply_warrior_bioform_leader_beasts", None) if tyr_mgr is not None else None
        if callable(apply_fn):
            apply_fn(unit)
        game = getattr(getattr(self, "player", None), "game", None)
        refresh_fn = getattr(game, "refresh_rule_subscribers", None) if game is not None else None
        if callable(refresh_fn):
            refresh_fn()
        return True

    # ---------- Command phase CP gain hooks ----------
    def has_tally_of_pestilence(self) -> bool:
        cached = self._has_tally_of_pestilence
        if cached is not None:
            return bool(cached)
        found = False
        for unit in list(getattr(self, "units", []) or []):
            if unit is None:
                continue
            iter_fn = getattr(unit, "_iter_ability_entries_for_rules", None)
            if not callable(iter_fn):
                continue
            for name, _desc in iter_fn(model=None):
                if str(name or "").strip().lower() == "tally of pestilence":
                    found = True
                    break
            if found:
                break
        self._has_tally_of_pestilence = found
        return found

    def _consume_tally_of_pestilence_bonus(self) -> int:
        if not self.has_tally_of_pestilence():
            return 0
        tally = int(getattr(self, "tally_of_pestilence", 0) or 0)
        if tally >= 7:
            self.tally_of_pestilence = 0
            return 1
        return 0

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
            if not getattr(u, "deployed", False):
                continue
            if not u.is_alive():
                continue
            if getattr(u, "reserve_status", "deployed") != "deployed":
                continue
            sr = getattr(u, "special_rules", {}) or {}
            if not isinstance(sr, dict):
                raise TypeError("special_rules must be a dict for CP gain parsing.")
            specs = list(sr.get("command_phase_bonus_cp_specs", []) or [])
            if specs:
                for spec in specs:
                    if not isinstance(spec, dict):
                        continue
                    try:
                        cp_gain = int(spec.get("cp", 0) or 0)
                    except Exception:
                        cp_gain = 0
                    if cp_gain <= 0:
                        continue
                    if bool(spec.get("requires_warlord", False)):
                        is_warlord = bool(getattr(u, "is_warlord", False)) or getattr(self, "warlord", None) is u
                        if not is_warlord:
                            continue
                    bonus += int(cp_gain)
                continue
            # Accept either key spelling; keep it simple.
            b = int(sr.get("command_phase_bonus_cp", sr.get("command_phase_cp_bonus", 0)) or 0)
            if b > 0:
                bonus += b
        bonus += self._consume_tally_of_pestilence_bonus()
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
            if bool(getattr(u, "is_attached_leader", False)):
                continue
            if bool(getattr(u, "is_joined_support", False)):
                continue
            if bool(getattr(u, "is_embarked", False)) or getattr(u, "embarked_in", None) is not None:
                continue
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
            uid = get_entity_id(u)
            if uid in seen:
                return
            seen.add(uid)
            members.append(u)

        _add(root)
        # attached leaders
        for l in list(getattr(root, "attached_leaders", []) or []):
            _add(l)
        # joined support artillery units
        for s in list(getattr(root, "attached_support_units", []) or []):
            _add(s)

        # transport passengers + their attached leaders
        if bool(getattr(root, "is_transport", False)) or bool(getattr(root, "transport_passengers", []) or []):
            for p in list(getattr(root, "transport_passengers", []) or []):
                _add(p)
                for l in list(getattr(p, "attached_leaders", []) or []):
                    _add(l)

        return members

    def _reserve_group_points(self, root: Unit) -> int:
        total = 0
        for u in self._reserve_group_members(root):
            total += int(u.get_unit_cost())
        return int(total)

    def _reserve_group_exempt_from_unit_cap(self, root: Unit) -> bool:
        if root is None:
            return False
        get_rule = getattr(root, "get_drop_pod_assault_rule", None)
        if not callable(get_rule):
            return False
        rule = get_rule()
        if not isinstance(rule, dict):
            return False
        return bool(rule.get("counts_not_towards_reserves_limit", False))

    def _reserve_group_counts_towards_unit_cap(self, root: Unit, *, decision: str) -> bool:
        status = str(decision or "").strip().lower()
        if status not in ("reserves", "strategic_reserves"):
            return False
        if self._reserve_group_exempt_from_unit_cap(root):
            return False
        return True

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

        # Some transport assault abilities are exempt from the reserves unit-count cap.
        counts_towards_units = self._reserve_group_counts_towards_unit_cap(unit, decision="reserves")

        # Check both unit count and points limits
        can_add_units = (current_reserve_units < limits['max_units']) if counts_towards_units else True
        can_add_points = current_reserve_points + unit_points <= limits['max_points']
        
        return can_add_units and can_add_points

    def get_current_reserves_decisions(self) -> dict[str, str]:
        decisions: dict[str, str] = {}
        for root in self._reserve_group_roots():
            decisions[get_entity_id(root)] = str(getattr(root, "reserve_status", "deployed") or "deployed")
        return decisions

    def validate_redeploy_to_strategic_reserves(
        self,
        root: Unit,
        *,
        ignore_unit_cap_root_ids: Optional[Set[str]] = None,
    ) -> dict:
        if root is None:
            return {
                "valid": False,
                "errors": ["Redeploy to Strategic Reserves requires a unit."],
                "reserve_units": 0,
                "reserve_points": 0,
                "strategic_points": 0,
                "limits": self.get_reserve_limits(),
            }
        get_root = getattr(root, "get_attached_unit_root", None)
        if callable(get_root):
            resolved_root = get_root()
            if resolved_root is not None:
                root = resolved_root
        decisions = self.get_current_reserves_decisions()
        decisions[get_entity_id(root)] = "strategic_reserves"
        return self.validate_reserves_decisions(
            decisions,
            ignore_unit_cap_root_ids=ignore_unit_cap_root_ids,
        )

    def validate_reserves_decisions(
        self,
        reserves_decisions: dict,
        *,
        ignore_unit_cap_root_ids: Optional[Set[str]] = None,
    ) -> dict:
        """
        Validate reserves decisions against the 50% limits.
        
        Args:
            reserves_decisions: Dict mapping unit ids to reserve status ('deploy', 'reserves', 'strategic_reserves')
            
        Returns:
            dict: Validation result with 'valid' boolean and 'errors' list
        """
        limits = self.get_reserve_limits()
        errors: List[str] = []
        ignored_unit_cap_root_ids = {
            str(value or "").strip()
            for value in set(ignore_unit_cap_root_ids or set())
            if str(value or "").strip()
        }

        reserve_units = 0
        reserve_points = 0
        strategic_points = 0

        def _must_start_in_reserves(u: Unit) -> bool:
            fn = getattr(u, "must_start_in_reserves", None)
            return bool(fn()) if callable(fn) else False

        roots = self._reserve_group_roots()
        for root in roots:
            rid = get_entity_id(root)
            decision = reserves_decisions.get(rid, "deploy")
            if _must_start_in_reserves(root):
                if decision == "deploy":
                    errors.append(f"{getattr(root, 'name', 'Unit')} must start in Reserves")
                decision = "reserves"
            if decision == "strategic_reserves":
                if bool(getattr(root, "is_fortification", False)):
                    errors.append(f"FORTIFICATIONS cannot be placed in Strategic Reserves: {getattr(root, 'name', 'Unit')}")
                    continue
            if decision in ["reserves", "strategic_reserves"]:
                counts_towards_unit_cap = self._reserve_group_counts_towards_unit_cap(root, decision=decision)
                if counts_towards_unit_cap and not (
                    decision == "strategic_reserves" and rid in ignored_unit_cap_root_ids
                ):
                    reserve_units += 1
                pts = self._reserve_group_points(root)
                reserve_points += pts
                if decision == "strategic_reserves":
                    strategic_points += int(
                        self._strategic_reserve_points_cost(root, pts, decision=decision)
                    )

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
            "ignored_unit_cap_root_ids": sorted(ignored_unit_cap_root_ids),
        }

    def enforce_reserves_limits(self, reserves_decisions: dict) -> dict:
        """
        Enforce reserve limits by modifying decisions if necessary.
        This ensures the final reserves decisions comply with the 50% limits.
        
        Args:
            reserves_decisions: Dict mapping unit ids to reserve status
            
        Returns:
            dict: Modified reserves decisions that comply with limits
        """
        limits = self.get_reserve_limits()
        modified = dict(reserves_decisions or {})

        roots = self._reserve_group_roots()

        def _root_key(u: Unit) -> str:
            return get_entity_id(u)

        def _must_start_in_reserves(u: Unit) -> bool:
            fn = getattr(u, "must_start_in_reserves", None)
            return bool(fn()) if callable(fn) else False

        # Normalize: ensure every root has an entry (default deploy)
        for r in roots:
            k = _root_key(r)
            if k not in modified:
                modified[k] = "deploy"

        # Hard rule: Fortifications cannot be Strategic Reserves.
        for r in roots:
            if not bool(getattr(r, "is_fortification", False)):
                continue
            k = _root_key(r)
            decision = modified.get(k, "deploy")
            if decision == "strategic_reserves":
                modified[k] = "deploy"

        # AIRCRAFT must start in Reserves: force decisions to standard reserves.
        for r in roots:
            if not _must_start_in_reserves(r):
                continue
            k = _root_key(r)
            decision = modified.get(k, "deploy")
            if decision != "reserves":
                modified[k] = "reserves"

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
                    decision = modified.get(k, "deploy")
                    if decision == "strategic_reserves" and not _must_start_in_reserves(r):
                        group_points = self._reserve_group_points(r)
                        strategic_cost = int(
                            self._strategic_reserve_points_cost(r, group_points, decision=decision)
                        )
                        if strategic_cost <= 0:
                            continue
                        strategic_roots.append((r, strategic_cost, group_points))
                strategic_roots.sort(key=lambda item: (item[1], item[2]), reverse=True)
                if not strategic_roots:
                    break
                r = strategic_roots[0][0]
                k = _root_key(r)
                # Prefer keeping in (standard) reserves if unit can Deep Strike; else deploy it.
                can_standard = bool(r.has_deep_strike()) or bool(self._ride_the_wind_allows_standard_reserves(r))
                modified[k] = "reserves" if can_standard else "deploy"
                continue

            # Enforce overall reserves caps (units/points): convert the highest-point reserve group to deploy until valid.
            reserve_roots = []
            for r in roots:
                k = _root_key(r)
                decision = modified.get(k, "deploy")
                if decision in ("reserves", "strategic_reserves") and not _must_start_in_reserves(r):
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
                decision = modified.get(k, "deploy")
                if decision in ("reserves", "strategic_reserves") and not _must_start_in_reserves(r):
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
            reserves_decisions: Dict mapping unit ids to reserve status
            
        Returns:
            dict: Current reserves status and limits
        """
        limits = self.get_reserve_limits()
        reserve_units = 0
        reserve_points = 0
        strategic_points = 0
        reserve_unit_names: List[str] = []
        strategic_reserve_unit_names: List[str] = []

        def _must_start_in_reserves(u: Unit) -> bool:
            fn = getattr(u, "must_start_in_reserves", None)
            return bool(fn()) if callable(fn) else False

        roots = self._reserve_group_roots()
        for root in roots:
            rid = get_entity_id(root)
            decision = reserves_decisions.get(rid, "deploy")
            if _must_start_in_reserves(root):
                decision = "reserves"
            if decision == "reserves":
                if self._reserve_group_counts_towards_unit_cap(root, decision=decision):
                    reserve_units += 1
                pts = self._reserve_group_points(root)
                reserve_points += pts
                reserve_unit_names.append(getattr(root, "name", "Unit"))
            elif decision == "strategic_reserves":
                if self._reserve_group_counts_towards_unit_cap(root, decision=decision):
                    reserve_units += 1
                pts = self._reserve_group_points(root)
                reserve_points += pts
                strategic_points += int(
                    self._strategic_reserve_points_cost(root, pts, decision=decision)
                )
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

    def _unit_cannot_be_warlord(self, unit: Unit) -> bool:
        sr = getattr(unit, "special_rules", None)
        return bool(isinstance(sr, dict) and sr.get("cannot_be_warlord"))

    def _unit_cannot_receive_enhancements(self, unit: Unit) -> bool:
        sr = getattr(unit, "special_rules", None)
        return bool(isinstance(sr, dict) and sr.get("cannot_be_given_enhancements"))

    def _unit_spawn_only(self, unit: Unit) -> bool:
        sr = getattr(unit, "special_rules", None)
        return bool(isinstance(sr, dict) and sr.get("spawn_only"))

    def _veterans_of_the_void_allows_enhancement(self, unit: Unit, enhancement: Enhancement) -> bool:
        ae_mgr = getattr(self, "aeldari_detachments", None)
        if ae_mgr is None:
            return False
        allows_fn = getattr(ae_mgr, "veterans_of_the_void_allows_enhancement", None)
        if not callable(allows_fn):
            return False
        return bool(allows_fn(unit, enhancement))

    def _normalize_upgrade_tag(self, value: object) -> str:
        text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        return re.sub(r"[^a-z0-9_]+", "", text)

    def _unit_upgrade_tags(self, unit: Unit) -> set[str]:
        tags: set[str] = set()
        raw_tags = list(getattr(unit, "upgrade_tags", []) or [])
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict):
            raw_tags.extend(list(sr.get("upgrade_tags", []) or []))
        metadata = dict(getattr(unit, "build_metadata", {}) or {})
        raw_tags.extend(list(metadata.get("upgrade_tags", []) or []))
        return {
            normalized
            for tag in raw_tags
            if (normalized := self._normalize_upgrade_tag(tag))
        }

    def _enhancement_assignment_metadata(
        self,
        unit: Unit,
        assignment_metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if isinstance(assignment_metadata, dict):
            return dict(assignment_metadata)
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict):
            stored = sr.get("enhancement_assignment_metadata", {})
            if isinstance(stored, dict):
                return dict(stored)
        return {}

    def _selected_upgrade_tag(
        self,
        unit: Unit,
        assignment_metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        metadata = self._enhancement_assignment_metadata(unit, assignment_metadata)
        candidates = [
            metadata.get("upgrade_tag"),
            metadata.get("upgradeTag"),
            metadata.get("selected_upgrade_tag"),
        ]
        for candidate in candidates:
            normalized = self._normalize_upgrade_tag(candidate)
            if normalized:
                return normalized
        return ""

    def _enhancement_allows_upgrade_tag_target(
        self,
        unit: Unit,
        enhancement: Enhancement,
        *,
        assignment_metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        raw_allowed_tags = tuple(getattr(enhancement, "eligible_upgrade_tags", ()) or ())
        allowed_tags = {
            self._normalize_upgrade_tag(tag)
            for tag in raw_allowed_tags
            if self._normalize_upgrade_tag(tag)
        }
        if not allowed_tags:
            return False
        unit_tags = self._unit_upgrade_tags(unit)
        if not unit_tags:
            return False
        selected_tag = self._selected_upgrade_tag(unit, assignment_metadata)
        if selected_tag:
            supports_tag = getattr(enhancement, "supports_upgrade_tag", None)
            if callable(supports_tag):
                return bool(supports_tag(selected_tag)) and selected_tag in unit_tags
            return selected_tag in allowed_tags and selected_tag in unit_tags
        return bool(unit_tags.intersection(allowed_tags))

    def _enhancement_allows_non_character_unit(
        self,
        unit: Unit,
        enhancement: Enhancement,
        *,
        assignment_metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        if self._veterans_of_the_void_allows_enhancement(unit, enhancement):
            return True
        return self._enhancement_allows_upgrade_tag_target(
            unit,
            enhancement,
            assignment_metadata=assignment_metadata,
        )

    def _veterans_of_the_void_max_enhancements(self) -> int:
        ae_mgr = getattr(self, "aeldari_detachments", None)
        if ae_mgr is None:
            return 3
        has_fn = getattr(ae_mgr, "has_veterans_of_the_void", None)
        if not callable(has_fn) or not bool(has_fn()):
            return 3
        cap_fn = getattr(ae_mgr, "veterans_of_the_void_max_enhancements", None)
        if not callable(cap_fn):
            return 3
        try:
            return max(0, int(cap_fn() or 0))
        except (TypeError, ValueError):
            return 3

    def _ride_the_wind_allows_standard_reserves(self, unit: Unit) -> bool:
        ae_mgr = getattr(self, "aeldari_detachments", None)
        if ae_mgr is None:
            return False
        allow_fn = getattr(ae_mgr, "ride_the_wind_allows_standard_reserves", None)
        if not callable(allow_fn):
            return False
        return bool(allow_fn(unit))

    def _strategic_reserve_points_cost(self, root: Unit, points: int, *, decision: str = "strategic_reserves") -> int:
        if str(decision or "").strip().lower() != "strategic_reserves":
            return 0
        if root is None:
            return int(points or 0)
        sm_mgr = getattr(self, "space_marines_detachments", None)
        ignore_fn = (
            getattr(sm_mgr, "company_of_hunters_master_of_manoeuvre_ignore_strategic_reserve_points", None)
            if sm_mgr is not None
            else None
        )
        if callable(ignore_fn) and bool(ignore_fn(root)):
            return 0
        return int(points or 0)

    def validate_spawn_only_units(self):
        for unit in self.units:
            if self._unit_spawn_only(unit) and not getattr(unit, "spawned_in_battle", False):
                raise ArmyValidationError(
                    f"Unit '{unit.name}' is spawn-only and cannot be mustered; it is created by other rules."
                )

    def get_pending_daemonic_allegiance_units(self) -> List[Unit]:
        pending: list[Unit] = []
        for unit in list(getattr(self, "units", []) or []):
            options_fn = getattr(unit, "get_daemonic_allegiance_options", None)
            options = list(options_fn() or []) if callable(options_fn) else []
            if not options:
                continue
            selection_fn = getattr(unit, "get_daemonic_allegiance_selection", None)
            selection = selection_fn() if callable(selection_fn) else None
            if selection:
                continue
            pending.append(unit)
        return pending

    def resolve_daemonic_allegiances(self, *, player=None, game=None) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_DAEMONIC_ALLEGIANCE
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.entity_ids import get_entity_id
        except Exception:
            return
        for unit in list(getattr(self, "units", []) or []):
            options_fn = getattr(unit, "get_daemonic_allegiance_options", None)
            options = list(options_fn() or []) if callable(options_fn) else []
            if not options:
                continue
            selection_fn = getattr(unit, "get_daemonic_allegiance_selection", None)
            selection = selection_fn() if callable(selection_fn) else None
            if selection:
                continue

            unit_id = get_entity_id(unit)
            queue = getattr(game, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_DAEMONIC_ALLEGIANCE:
                        continue
                    ctx = getattr(req, "context", {}) or {}
                    if str(ctx.get("unit_id", "")) == str(unit_id):
                        break
                else:
                    req_options = []
                    for opt in options:
                        if isinstance(opt, (list, tuple)):
                            keyword = str(opt[0]) if opt else ""
                            wargear = str(opt[1]) if len(opt) > 1 else ""
                        else:
                            keyword = str(opt)
                            wargear = ""
                        if not keyword:
                            continue
                        req_options.append(
                            DecisionOption.create(
                                keyword,
                                payload={"keyword": keyword, "wargear_name": wargear, "unit_id": unit_id},
                            )
                        )
                    if not req_options:
                        continue
                    req = DecisionRequest.create(
                        DECISION_CHOOSE_DAEMONIC_ALLEGIANCE,
                        f"Select Daemonic Allegiance for {getattr(unit, 'name', 'Unit')}.",
                        player_id=getattr(player, "id", None),
                        options=req_options,
                        context={"unit_id": unit_id},
                    )
                    if hasattr(game, "request_decision"):
                        game.request_decision(req)

    def validate_daemonic_allegiances(self) -> None:
        missing: list[str] = []
        for unit in list(getattr(self, "units", []) or []):
            options_fn = getattr(unit, "get_daemonic_allegiance_options", None)
            options = list(options_fn() or []) if callable(options_fn) else []
            if not options:
                continue
            selection_fn = getattr(unit, "get_daemonic_allegiance_selection", None)
            selection = selection_fn() if callable(selection_fn) else None
            if not selection:
                missing.append(getattr(unit, "name", "Unknown"))
                continue
            valid = {kw.lower() for kw, _ in options}
            if str(selection).strip().lower() not in valid:
                raise ArmyValidationError(
                    f"Daemonic Allegiance selection '{selection}' is not valid for unit '{unit.name}'."
                )
            apply_fn = getattr(unit, "apply_daemonic_allegiance_selection", None)
            if not callable(apply_fn):
                raise ArmyValidationError(
                    f"Unit '{unit.name}' cannot apply Daemonic Allegiance selections."
                )
            apply_fn(selection)
        if missing:
            names = ", ".join(missing)
            raise ArmyValidationError(
                f"Daemonic Allegiance requires a keyword selection for: {names}."
            )

    def add_enhancement(
        self,
        enhancement,
        character_unit,
        *,
        assignment_metadata: Optional[dict[str, Any]] = None,
    ):
        invalidate_cache = getattr(character_unit, "_invalidate_ability_cache", None)

        # Assign an Enhancement to a Character unit or an explicitly tagged upgrade target.
        allows_non_character = self._enhancement_allows_non_character_unit(
            character_unit,
            enhancement,
            assignment_metadata=assignment_metadata,
        )
        if character_unit.is_epic_hero:
            raise ArmyValidationError(
                f"Enhancements can only be assigned to non-Epic Hero Characters. '{character_unit.name}' is not eligible."
            )
        if not allows_non_character and not character_unit.is_character:
            raise ArmyValidationError(
                f"Enhancements can only be assigned to non-Epic Hero Characters. '{character_unit.name}' is not eligible."
            )
        if self._unit_cannot_receive_enhancements(character_unit):
            raise ArmyValidationError(f"Character '{character_unit.name}' cannot be given Enhancements.")
        if character_unit.enhancement:
            raise ArmyValidationError(f"Character '{character_unit.name}' already has an Enhancement.")
        # Enhancements are detachment-specific in 10e; enforce faction and detachment match when available.
        if getattr(self, "faction_id", None) and getattr(enhancement, "faction_id", ""):
            if self.faction_id != enhancement.faction_id:
                raise ArmyValidationError(
                    f"Enhancement '{enhancement.name}' belongs to faction {enhancement.faction_id}, "
                    f"but army faction is {self.faction_id}."
                )
        if self.get_detachment_types() and getattr(enhancement, "detachment", ""):
            mgr = self.get_detachment_manager_for_faction(getattr(enhancement, "faction_id", "") or self.faction_id)
            if mgr is not None:
                if not mgr.detachment_matches(enhancement.detachment):
                    raise ArmyValidationError(
                        f"Enhancement '{enhancement.name}' is for detachment '{enhancement.detachment}', "
                        f"but army detachments are '{', '.join(self.get_detachment_types())}'."
                    )
            elif not self.has_detachment_type(enhancement.detachment):
                raise ArmyValidationError(
                    f"Enhancement '{enhancement.name}' is for detachment '{enhancement.detachment}', "
                    f"but army detachments are '{', '.join(self.get_detachment_types())}'."
                )
        eligibility_fn = getattr(enhancement, "is_unit_eligible", None)
        if callable(eligibility_fn) and not eligibility_fn(character_unit):
            clause = str(getattr(enhancement, "eligibility_clause", "") or "").strip()
            if clause:
                raise ArmyValidationError(
                    f"Enhancement '{enhancement.name}' can only be taken by {clause} model(s) only."
                )
            raise ArmyValidationError(
                f"Enhancement '{enhancement.name}' has model-only eligibility requirements that '{character_unit.name}' does not meet."
            )
        character_unit.enhancement = enhancement
        if callable(invalidate_cache):
            invalidate_cache()
        metadata = self._enhancement_assignment_metadata(character_unit, assignment_metadata)
        if metadata:
            sr = getattr(character_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["enhancement_assignment_metadata"] = metadata
            selected_upgrade_tag = self._selected_upgrade_tag(character_unit, metadata)
            if selected_upgrade_tag:
                sr["enhancement_upgrade_tag"] = selected_upgrade_tag
            character_unit.special_rules = sr
        apply_fn = getattr(enhancement, "apply_to_unit", None)
        if callable(apply_fn):
            apply_fn(character_unit)
        if callable(invalidate_cache):
            invalidate_cache()
        self.enhancements.append(enhancement)

    def select_warlord(self, unit: Unit):
        if not unit.is_character:
            raise ArmyValidationError(f"Only Character units can be selected as Warlord. '{unit.name}' is not a Character.")
        if self._unit_cannot_be_warlord(unit):
            raise ArmyValidationError(f"Unit '{unit.name}' cannot be your Warlord.")
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

    def validate_unique_model_restrictions(self) -> None:
        def _norm_name(value: str) -> str:
            text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())
            return re.sub(r"\s+", " ", text).strip()

        units = list(getattr(self, "units", []) or [])
        unit_counts: dict[str, int] = {}
        display_names: dict[str, str] = {}
        for unit in units:
            if unit is None:
                continue
            key = _norm_name(getattr(unit, "name", ""))
            if not key:
                continue
            unit_counts[key] = int(unit_counts.get(key, 0)) + 1
            if key not in display_names:
                display_names[key] = str(getattr(unit, "name", "") or "Unknown").strip() or "Unknown"

        restricted_caps: dict[str, dict] = {}
        for unit in units:
            if unit is None:
                continue

            unit_key = _norm_name(getattr(unit, "name", ""))
            has_rule = bool(getattr(unit, "has_unique_model_restriction", lambda: False)())
            if has_rule and unit_key:
                existing = restricted_caps.get(unit_key)
                if existing is None or int(existing.get("limit", 0)) > 1:
                    restricted_caps[unit_key] = {
                        "unit_name": display_names.get(unit_key, str(getattr(unit, "name", "") or "Unknown")),
                        "limit": 1,
                    }

            get_caps = getattr(unit, "get_named_unit_inclusion_caps", None)
            if not callable(get_caps):
                continue
            for cap in list(get_caps() or []):
                cap_key = _norm_name(str(cap.get("unit_key") or cap.get("unit_name") or ""))
                if not cap_key:
                    continue
                try:
                    cap_limit = int(cap.get("limit"))
                except (TypeError, ValueError):
                    continue
                if cap_limit <= 0:
                    continue
                existing = restricted_caps.get(cap_key)
                if existing is None or int(existing.get("limit", 0)) > cap_limit:
                    restricted_caps[cap_key] = {
                        "unit_name": str(cap.get("unit_name") or cap_key).strip(),
                        "limit": cap_limit,
                    }

        override_sources = list(getattr(self, "detachment_managers", {}).values() or [])
        fallback_mgr = getattr(self, "aeldari_detachments", None)
        if fallback_mgr is not None and all(fallback_mgr is not mgr for mgr in override_sources):
            override_sources.append(fallback_mgr)
        for mgr in override_sources:
            if mgr is None:
                continue
            get_overrides = getattr(mgr, "get_unique_model_cap_overrides", None)
            if not callable(get_overrides):
                continue
            for cap in list(get_overrides() or []):
                cap_key = _norm_name(str(cap.get("unit_key") or cap.get("unit_name") or ""))
                if not cap_key:
                    continue
                try:
                    cap_limit = int(cap.get("limit"))
                except (TypeError, ValueError):
                    continue
                if cap_limit <= 0:
                    continue
                unit_name = str(cap.get("unit_name") or display_names.get(cap_key) or cap_key).strip() or cap_key
                restricted_caps[cap_key] = {
                    "unit_name": unit_name,
                    "limit": cap_limit,
                }

        violations = []
        for cap_key in sorted(restricted_caps):
            spec = restricted_caps[cap_key]
            limit = int(spec.get("limit", 0))
            count = int(unit_counts.get(cap_key, 0))
            if count <= limit:
                continue
            label = display_names.get(cap_key, str(spec.get("unit_name") or cap_key).strip() or "Unknown")
            violations.append(f"{label} ({count}/{limit})")

        if violations:
            joined = ", ".join(violations)
            raise ArmyValidationError(f"Unique model restriction: {joined}.")

    def validate_ynnari_epic_hero_restrictions(self) -> None:
        def _norm_name(value: str) -> str:
            text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())
            return re.sub(r"\s+", " ", text).strip()

        def _has_keyword(unit, keyword: str) -> bool:
            if unit is None:
                return False
            fn = getattr(unit, "has_any_keyword", None)
            if callable(fn):
                return bool(fn(keyword))
            kw = (keyword or "").strip().upper()
            if not kw:
                return False
            keywords = [
                str(k).strip().upper()
                for k in (getattr(unit, "keywords", []) or [])
                if str(k).strip()
            ]
            faction_keywords = [
                str(k).strip().upper()
                for k in (getattr(unit, "faction_keywords", []) or [])
                if str(k).strip()
            ]
            return kw in set(keywords + faction_keywords)

        def _is_ynnari_unit(unit) -> bool:
            if unit is None:
                return False
            if _has_keyword(unit, "YNNARI"):
                return True
            name_norm = _norm_name(getattr(unit, "name", ""))
            return name_norm in {"yvraine", "the visarch", "the yncarne"}

        units = list(getattr(self, "units", []) or [])
        if not units:
            return

        visarch_present = any(_norm_name(getattr(u, "name", "")) == "the visarch" for u in units)
        yvraine_present = any(_norm_name(getattr(u, "name", "")) == "yvraine" for u in units)
        yncarne_present = any(_norm_name(getattr(u, "name", "")) == "the yncarne" for u in units)
        if not visarch_present and not yvraine_present and not yncarne_present:
            return

        non_ynnari_epic = [
            u for u in units
            if getattr(u, "is_epic_hero", False) and not _is_ynnari_unit(u)
        ]
        if not non_ynnari_epic:
            return
        names = ", ".join(sorted({getattr(u, "name", "Unknown") for u in non_ynnari_epic}))
        if visarch_present:
            raise ArmyValidationError(
                f"The Visarch restriction: cannot include non-Ynnari Epic Hero units ({names})."
            )
        if yvraine_present:
            raise ArmyValidationError(
                f"Yvraine restriction: cannot include non-Ynnari Epic Hero units ({names})."
            )
        if yncarne_present:
            raise ArmyValidationError(
                f"The Yncarne restriction: cannot include non-Ynnari Epic Hero units ({names})."
            )

    def validate_tau_independent_power(self) -> None:
        """
        T'au Empire - Commander Farsight, INDEPENDENT POWER:
        - If your army includes Commander Farsight, it cannot include any ETHEREAL units.
        - If your army includes any ETHEREAL units, it cannot include Commander Farsight.
        """
        units = list(getattr(self, "units", []) or [])
        if not units:
            return

        def _norm_name(value: str) -> str:
            text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())
            return re.sub(r"\s+", " ", text).strip()

        def _has_keyword(unit, keyword: str) -> bool:
            if unit is None:
                return False
            fn = getattr(unit, "has_any_keyword", None)
            if callable(fn):
                return bool(fn(keyword))
            kw = str(keyword or "").strip().upper()
            if not kw:
                return False
            keywords = [
                str(k).strip().upper()
                for k in (getattr(unit, "keywords", []) or [])
                if str(k).strip()
            ]
            faction_keywords = [
                str(k).strip().upper()
                for k in (getattr(unit, "faction_keywords", []) or [])
                if str(k).strip()
            ]
            return kw in set(keywords + faction_keywords)

        farsight_units = [
            unit for unit in units
            if _norm_name(getattr(unit, "name", "")) == "commander farsight"
        ]
        if not farsight_units:
            return

        ethereal_units = [
            unit for unit in units
            if _has_keyword(unit, "ETHEREAL")
        ]
        if not ethereal_units:
            return

        ethereal_names = ", ".join(sorted({str(getattr(unit, "name", "Unknown") or "Unknown") for unit in ethereal_units}))
        raise ArmyValidationError(
            "INDEPENDENT POWER: armies that include Commander Farsight cannot include ETHEREAL units "
            f"({ethereal_names})."
        )

    def validate_leaders(self):
        from .army_attachment_runtime import validate_leader_attachments

        validate_leader_attachments(self)

    def apply_authored_attachment_bindings(self) -> dict[str, int]:
        from .army_attachment_runtime import apply_authored_attachment_bindings

        return apply_authored_attachment_bindings(self)

    @staticmethod
    def _unit_matches_name_or_datasheet_id(unit, *, normalized_name: str, datasheet_id: str) -> bool:
        if unit is None:
            return False
        name_norm = re.sub(r"[^a-z0-9]+", " ", str(getattr(unit, "name", "") or "").lower()).strip()
        name_norm = re.sub(r"\s+", " ", name_norm).strip()
        if normalized_name and name_norm == normalized_name:
            return True
        get_dsid = getattr(unit, "get_datasheet_id", None)
        if callable(get_dsid):
            return str(get_dsid() or "").strip() == str(datasheet_id or "").strip()
        return False

    @staticmethod
    def _append_unique_case_insensitive(values: list[str], value: str) -> list[str]:
        target = str(value or "").strip()
        if not target:
            return list(values or [])
        existing = list(values or [])
        lowered = {str(item or "").strip().lower() for item in existing}
        if target.lower() not in lowered:
            existing.append(target)
        return existing

    def _apply_chapter_master_of_the_raven_guard(self) -> None:
        units = list(getattr(self, "units", []) or [])
        if not units:
            return
        aethon_units = [
            unit for unit in units
            if self._unit_matches_name_or_datasheet_id(
                unit,
                normalized_name="aethon shaan",
                datasheet_id=_AETHON_SHAAN_DATASHEET_ID,
            )
        ]
        shrike_units = [
            unit for unit in units
            if self._unit_matches_name_or_datasheet_id(
                unit,
                normalized_name="kayvaan shrike",
                datasheet_id=_KAYVAAN_SHRIKE_DATASHEET_ID,
            )
        ]
        if not aethon_units or not shrike_units:
            return

        has_rule = False
        for source in aethon_units:
            if _unit_has_named_ability_for_rules(source, "CHAPTER MASTER OF THE RAVEN GUARD"):
                has_rule = True
                break
            for name, desc in _iter_unit_ability_entries_for_rules(source):
                text = _normalize_ability_text_for_rules(desc or name)
                if _CHAPTER_MASTER_OF_THE_RAVEN_GUARD_MARKER in text:
                    has_rule = True
                    break
            if has_rule:
                break
        if not has_rule:
            return

        for shrike in shrike_units:
            sr = getattr(shrike, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}

            disabled = list(sr.get("disabled_ability_names", []) or [])
            disabled = self._append_unique_case_insensitive(disabled, "Lone Operative")
            sr["disabled_ability_names"] = disabled

            removed_keywords = list(sr.get("ability_removed_keywords", []) or [])
            removed_keywords = self._append_unique_case_insensitive(removed_keywords, "CHAPTER MASTER")
            sr["ability_removed_keywords"] = removed_keywords

            added_keywords = list(sr.get("ability_added_keywords", []) or [])
            added_keywords = self._append_unique_case_insensitive(added_keywords, "CAPTAIN")
            sr["ability_added_keywords"] = added_keywords
            sr["chapter_master_of_the_raven_guard_applied"] = True
            shrike.special_rules = sr

            invalidate = getattr(shrike, "_invalidate_ability_cache", None)
            if callable(invalidate):
                invalidate()

    def apply_declare_battle_formations_restrictions(self) -> None:
        """Apply non-optional, start-of-Declare-Battle-Formations datasheet restrictions."""
        self._apply_chapter_master_of_the_raven_guard()

    def _unit_has_company_heroes_restriction(self, unit: Unit) -> bool:
        if unit is None:
            return False
        if _unit_has_named_ability_for_rules(unit, "COMPANY HEROES"):
            return True
        for name, desc in _iter_unit_ability_entries_for_rules(unit):
            text = _normalize_ability_text_for_rules(desc or name)
            if _COMPANY_HEROES_MUSTERING_MARKER in text:
                return True
        return False

    def _leader_satisfies_company_heroes_requirement(self, leader: Unit) -> bool:
        if leader is None:
            return False
        has_kw = getattr(leader, "has_any_keyword", None)
        if callable(has_kw):
            if bool(has_kw("CAPTAIN")) or bool(has_kw("CHAPTER MASTER")):
                return True
        keywords = [
            str(k).strip().upper()
            for k in (list(getattr(leader, "keywords", []) or []) + list(getattr(leader, "faction_keywords", []) or []))
            if str(k).strip()
        ]
        return "CAPTAIN" in keywords or "CHAPTER MASTER" in keywords

    def _validate_company_heroes_mandatory_leader(self) -> None:
        company_heroes_units = [
            unit for unit in list(getattr(self, "units", []) or [])
            if self._unit_has_company_heroes_restriction(unit)
        ]
        if not company_heroes_units:
            return

        units_to_remove: list[Unit] = []
        for company_heroes in company_heroes_units:
            attached = list(getattr(company_heroes, "attached_leaders", []) or [])
            if any(self._leader_satisfies_company_heroes_requirement(leader) for leader in attached):
                continue

            eligible_leaders: list[Unit] = []
            for candidate in list(getattr(self, "units", []) or []):
                if candidate is None or not bool(getattr(candidate, "is_leader", False)):
                    continue
                if not self._leader_satisfies_company_heroes_requirement(candidate):
                    continue
                can_attach = getattr(candidate, "can_attach_to", None)
                if callable(can_attach):
                    if not bool(can_attach(company_heroes)):
                        continue
                eligible_leaders.append(candidate)

            if eligible_leaders:
                names = ", ".join(
                    sorted(
                        {
                            str(getattr(candidate, "name", "Unknown") or "Unknown")
                            for candidate in eligible_leaders
                        }
                    )
                )
                suffix = f" Eligible Leaders: {names}." if names else "."
                raise ArmyValidationError(
                    f"Unit '{company_heroes.name}' must have one attached CAPTAIN or CHAPTER MASTER model "
                    "during Declare Battle Formations."
                    f"{suffix}"
                )

            units_to_remove.append(company_heroes)

        for company_heroes in units_to_remove:
            if company_heroes not in self.units:
                continue
            self.units.remove(company_heroes)
            sr = getattr(company_heroes, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["destroyed_before_battle"] = True
            sr["destroyed_before_battle_reason"] = (
                "COMPANY HEROES mandatory CAPTAIN/CHAPTER MASTER attachment was impossible."
            )
            company_heroes.special_rules = sr
            logger.info(
                "Declare Battle Formations: removed '%s' as destroyed because no eligible CAPTAIN/CHAPTER MASTER leader was available for COMPANY HEROES.",
                getattr(company_heroes, "name", "Unknown"),
            )

    def validate_support_artillery(self):
        """Validate joined-support attachments (Support Artillery + retinue-style joins)."""
        self.apply_declare_battle_formations_restrictions()
        from .army_attachment_runtime import validate_support_attachments

        validate_support_attachments(self)
        self._validate_company_heroes_mandatory_leader()

    def validate_enhancements(self):
        # Rule 1: Maximum enhancements (Veterans of the Void overrides core cap).
        max_enhancements = int(self._veterans_of_the_void_max_enhancements() or 0)
        if len(self.enhancements) > max_enhancements:
            if max_enhancements == 3:
                raise ArmyValidationError(f"Army has more than 3 Enhancements assigned.")
            raise ArmyValidationError(
                f"Veterans of the Void: army has {len(self.enhancements)} Enhancements assigned (max {max_enhancements})."
            )

        # Rule 2: Enhancements cannot be duplicated
        enhancement_names = [enhancement.name for enhancement in self.enhancements]
        if len(enhancement_names) != len(set(enhancement_names)):
            duplicates = [name for name in enhancement_names if enhancement_names.count(name) > 1]
            raise ArmyValidationError(f"Enhancements {duplicates} are assigned more than once.")

        # Rule 3: Enhancements can only be assigned to non-Epic Hero Characters
        for unit in self.units:
            if unit.enhancement:
                allows_non_character = self._enhancement_allows_non_character_unit(unit, unit.enhancement)
                if unit.is_epic_hero:
                    raise ArmyValidationError(f"Epic Hero '{unit.name}' cannot have Enhancements assigned.")
                if not allows_non_character and not unit.is_character:
                    raise ArmyValidationError(
                        f"Enhancements can only be assigned to non-Epic Hero Characters. '{unit.name}' is not eligible."
                    )
                if self._unit_cannot_receive_enhancements(unit):
                    raise ArmyValidationError(f"Unit '{unit.name}' cannot be given Enhancements.")
                eligibility_fn = getattr(unit.enhancement, "is_unit_eligible", None)
                if callable(eligibility_fn) and not eligibility_fn(unit):
                    clause = str(getattr(unit.enhancement, "eligibility_clause", "") or "").strip()
                    if clause:
                        raise ArmyValidationError(
                            f"Enhancement '{unit.enhancement.name}' can only be taken by {clause} model(s) only."
                        )
                    raise ArmyValidationError(
                        f"Enhancement '{unit.enhancement.name}' has model-only eligibility requirements that '{unit.name}' does not meet."
                    )

    def validate_warlord(self):
        # Ensure exactly one Warlord is selected
        warlord_units = [unit for unit in self.units if unit.is_warlord]
        if len(warlord_units) != 1:
            raise ArmyValidationError(f"Army must have exactly one Warlord. Found: {len(warlord_units)}.")
        if self._unit_cannot_be_warlord(warlord_units[0]):
            raise ArmyValidationError(f"Unit '{warlord_units[0].name}' cannot be your Warlord.")

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
        faction_id = (getattr(self, "faction_id", "") or "").strip().upper()
        if not faction_id:
            return
        for pact in pact_restrictions_for_faction(faction_id):
            if self._army_faction_matches_pact(pact.get("forbidden", "")):
                raise ArmyValidationError(
                    f"{pact.get('name', 'Pact')}: armies cannot select '{pact.get('forbidden', '').strip()}' as their Army Faction."
                )

        ec_mgr = getattr(self, "emperors_children", None)
        if ec_mgr is not None:
            for msg in list(ec_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))
        csm_mgr = getattr(self, "chaos_space_marines_detachments", None)
        if csm_mgr is not None and hasattr(csm_mgr, "validate_detachment_rules"):
            for msg in list(csm_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))
        we_mgr = getattr(self, "world_eaters_detachments", None)
        if we_mgr is not None:
            for msg in list(we_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))
        dg_mgr = getattr(self, "death_guard_detachments", None)
        if dg_mgr is not None and hasattr(dg_mgr, "validate_detachment_rules"):
            for msg in list(dg_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))
        cd_mgr = getattr(self, "chaos_daemons_detachments", None)
        if cd_mgr is not None:
            for msg in list(cd_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))
        ae_mgr = getattr(self, "aeldari_detachments", None)
        if ae_mgr is not None:
            for msg in list(ae_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))
        ia_mgr = getattr(self, "imperial_agents_detachments", None)
        if ia_mgr is not None:
            for msg in list(ia_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))
        ts_mgr = getattr(self, "thousand_sons_detachments", None)
        if ts_mgr is not None:
            for msg in list(ts_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))
        tyr_mgr = getattr(self, "tyranids_detachments", None)
        if tyr_mgr is not None:
            for msg in list(tyr_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))
        gsc_mgr = getattr(self, "genestealer_cults_detachments", None)
        if gsc_mgr is not None and hasattr(gsc_mgr, "validate_detachment_rules"):
            for msg in list(gsc_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))
        ne_mgr = getattr(self, "necrons_detachments", None)
        if ne_mgr is not None and hasattr(ne_mgr, "validate_detachment_rules"):
            for msg in list(ne_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))
        ik_mgr = getattr(self, "imperial_knights_detachments", None)
        if ik_mgr is not None and hasattr(ik_mgr, "validate_detachment_rules"):
            for msg in list(ik_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))
        ck_mgr = getattr(self, "chaos_knights_detachments", None)
        if ck_mgr is not None and hasattr(ck_mgr, "validate_detachment_rules"):
            for msg in list(ck_mgr.validate_detachment_rules() or []):
                if msg:
                    raise ArmyValidationError(str(msg))

    def _detachment_matches_pact(self, detachment: str, forbidden: str) -> bool:
        def _norm(text: str) -> str:
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

    def _army_faction_matches_pact(self, forbidden: str) -> bool:
        name = (getattr(self, "faction", "") or "").strip()
        if name and self._detachment_matches_pact(name, forbidden):
            return True
        for kw in list(getattr(self, "faction_keyword", []) or []):
            if self._detachment_matches_pact(str(kw), forbidden):
                return True
        return False

    def validate_space_marine_chapters(self) -> None:
        fid = str(getattr(self, "faction_id", "") or "").strip().upper()
        if fid != "SM":
            return

        def _unit_has_keyword(unit, keyword: str) -> bool:
            if unit is None:
                return False
            fn = getattr(unit, "has_any_keyword", None)
            if callable(fn):
                return bool(fn(keyword))
            kw = (keyword or "").strip().upper()
            if not kw:
                return False
            keywords = [
                str(k).strip().upper()
                for k in (getattr(unit, "keywords", []) or [])
                if str(k).strip()
            ]
            faction_keywords = [
                str(k).strip().upper()
                for k in (getattr(unit, "faction_keywords", []) or [])
                if str(k).strip()
            ]
            return kw in set(keywords + faction_keywords)

        def _unit_is_psyker(unit) -> bool:
            if unit is None:
                return False
            val = getattr(unit, "is_psyker", False)
            if callable(val):
                val = val()
            return bool(val)

        def _norm_name(name: str) -> str:
            txt = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower())
            return re.sub(r"\s+", " ", txt).strip()

        def _unit_has_crimson_fists_restriction(unit) -> bool:
            if _unit_has_named_ability_for_rules(unit, "CRIMSON FISTS"):
                return True
            marker = (
                "cannot be included in an army that includes any other "
                "imperial fists epic hero models"
            )
            for name, desc in _iter_unit_ability_entries_for_rules(unit):
                text = _normalize_ability_text_for_rules(desc or name)
                if marker in text:
                    return True
            return False

        astartes_units = [u for u in list(getattr(self, "units", []) or []) if _unit_has_keyword(u, "ADEPTUS ASTARTES")]
        if not astartes_units:
            return

        committed_chapter = None
        mgr = getattr(self, "space_marines_detachments", None)
        if mgr is not None:
            get_chapter = getattr(mgr, "get_committed_chapter_keyword", None)
            committed_chapter = get_chapter() if callable(get_chapter) else None

        def _unit_chapter_keywords(unit) -> list[str]:
            chapters: list[str] = []
            fks = list(getattr(unit, "faction_keywords", []) or [])
            for kw in fks:
                kw_u = str(kw).strip().upper()
                if not kw_u:
                    continue
                if kw_u == "ADEPTUS ASTARTES":
                    continue
                if kw_u == SPACE_MARINE_DEFAULT_CHAPTER:
                    continue
                if kw_u in SPACE_MARINE_ALLOWED_NON_CHAPTER_FACTION_KEYWORDS:
                    continue
                if kw_u not in chapters:
                    chapters.append(kw_u)
            if not chapters:
                for ch in SPACE_MARINE_EXPLICIT_CHAPTERS:
                    if _unit_has_keyword(unit, ch):
                        if ch not in chapters:
                            chapters.append(ch)
            return chapters

        def _is_kill_team_cassius(unit_name: str) -> bool:
            return _norm_name(unit_name).startswith("kill team cassius")

        def _is_mission_tactics_ability(ability) -> bool:
            if isinstance(ability, str):
                name = ability
            else:
                name = getattr(ability, "name", "")
            return str(name or "").strip().lower() == "mission tactics"

        def _toggle_mission_tactics(unit, *, enabled: bool) -> None:
            invalidate = getattr(unit, "_invalidate_ability_cache", None)
            if enabled:
                stored = getattr(unit, "_mission_tactics_original_abilities", None)
                if stored is not None:
                    unit.possible_abilities = list(stored)
                    if hasattr(unit, "_mission_tactics_original_abilities"):
                        delattr(unit, "_mission_tactics_original_abilities")
                    if callable(invalidate):
                        invalidate()
                return
            abilities = list(getattr(unit, "possible_abilities", []) or [])
            if not abilities:
                return
            if not any(_is_mission_tactics_ability(ab) for ab in abilities):
                return
            if getattr(unit, "_mission_tactics_original_abilities", None) is None:
                unit._mission_tactics_original_abilities = list(abilities)
            unit.possible_abilities = [ab for ab in abilities if not _is_mission_tactics_ability(ab)]
            if callable(invalidate):
                invalidate()

        chapter_present = set()

        for unit in astartes_units:
            unit_chapters = _unit_chapter_keywords(unit)
            if len(unit_chapters) > 1:
                raise ArmyValidationError(
                    f"Unit '{getattr(unit, 'name', 'Unknown')}' has multiple Chapter keywords: {unit_chapters}."
                )
            if unit_chapters:
                chapter_present.update(unit_chapters)

        if committed_chapter:
            chapter_present.add(committed_chapter)

        if len(chapter_present) > 1:
            raise ArmyValidationError(
                f"Space Marine armies cannot include units from more than one Chapter ({sorted(chapter_present)})."
            )

        has_black_templars = bool(committed_chapter == "BLACK TEMPLARS") or any(
            _unit_has_keyword(u, "BLACK TEMPLARS") for u in astartes_units
        )
        has_deathwatch = bool(committed_chapter == "DEATHWATCH") or any(
            _unit_has_keyword(u, "DEATHWATCH") for u in astartes_units
        )
        has_space_wolves = bool(committed_chapter == "SPACE WOLVES") or any(
            _unit_has_keyword(u, "SPACE WOLVES") for u in astartes_units
        )
        crimson_fists_units = [u for u in astartes_units if _unit_has_crimson_fists_restriction(u)]

        bt_banned = {_norm_name(n) for n in BLACK_TEMPLARS_FORBIDDEN_UNITS}
        dw_banned = {_norm_name(n) for n in DEATHWATCH_FORBIDDEN_UNITS}
        sw_banned = {_norm_name(n) for n in SPACE_WOLVES_FORBIDDEN_UNITS}

        if has_black_templars:
            mgr = getattr(self, "space_marines_detachments", None)
            if mgr is not None and mgr.detachment_matches("1st Company Task Force"):
                raise ArmyValidationError(
                    "Black Templars armies cannot use the 1st Company Task Force detachment."
                )

        if crimson_fists_units:
            imperial_fists_epic_heroes = [
                unit for unit in astartes_units
                if _unit_has_keyword(unit, "IMPERIAL FISTS") and _unit_has_keyword(unit, "EPIC HERO")
            ]
            for crimson_unit in crimson_fists_units:
                conflicting_units = [unit for unit in imperial_fists_epic_heroes if unit is not crimson_unit]
                if not conflicting_units:
                    continue
                conflict_names = ", ".join(
                    sorted(str(getattr(unit, "name", "Unknown") or "Unknown") for unit in conflicting_units)
                )
                raise ArmyValidationError(
                    "CRIMSON FISTS: "
                    f"'{getattr(crimson_unit, 'name', 'Unknown')}' cannot be included in an army that "
                    f"includes other IMPERIAL FISTS EPIC HERO units ({conflict_names})."
                )

        for unit in list(getattr(self, "units", []) or []):
            unit_name = getattr(unit, "name", "Unknown")
            unit_norm = _norm_name(unit_name)
            is_astartes = _unit_has_keyword(unit, "ADEPTUS ASTARTES")

            if has_black_templars and is_astartes:
                if _unit_is_psyker(unit):
                    raise ArmyValidationError(
                        f"Black Templars armies cannot include ADEPTUS ASTARTES PSYKER units ({unit_name})."
                    )
                if unit_norm in bt_banned and not _unit_has_keyword(unit, "BLACK TEMPLARS"):
                    raise ArmyValidationError(
                        f"Black Templars armies cannot include {unit_name} without the BLACK TEMPLARS keyword."
                    )

            if has_deathwatch:
                if is_astartes and not _unit_has_keyword(unit, "DEATHWATCH"):
                    raise ArmyValidationError(
                        f"Deathwatch armies cannot include ADEPTUS ASTARTES units from other Chapters ({unit_name})."
                    )
                if _unit_has_keyword(unit, "AGENTS OF THE IMPERIUM") and _unit_has_keyword(unit, "DEATHWATCH"):
                    if not _is_kill_team_cassius(unit_name):
                        raise ArmyValidationError(
                            "Deathwatch armies cannot include AGENTS OF THE IMPERIUM DEATHWATCH units "
                            f"({unit_name}), except Kill Team Cassius."
                        )
                if is_astartes and unit_norm in dw_banned:
                    raise ArmyValidationError(
                        f"Deathwatch armies cannot include {unit_name}."
                    )

            if has_space_wolves and is_astartes and unit_norm in sw_banned:
                raise ArmyValidationError(
                    f"Space Wolves armies cannot include {unit_name}."
                )

        is_black_spear = False
        mgr = getattr(self, "space_marines_detachments", None)
        if mgr is not None:
            is_black_spear = bool(mgr.detachment_matches("Black Spear Task Force"))

        if has_deathwatch:
            for unit in list(getattr(self, "units", []) or []):
                _toggle_mission_tactics(unit, enabled=is_black_spear)

    def validate_dreadblades(self) -> None:
        fid = str(getattr(self, "faction_id", "") or "").strip().upper()
        if fid == "QT":
            return

        def _has_keyword(unit, keyword: str) -> bool:
            if unit is None:
                return False
            fn = getattr(unit, "has_any_keyword", None)
            if callable(fn):
                return bool(fn(keyword))
            kw = (keyword or "").strip().upper()
            if not kw:
                return False
            keywords = [
                str(k).strip().upper()
                for k in (getattr(unit, "keywords", []) or [])
                if str(k).strip()
            ]
            faction_keywords = [
                str(k).strip().upper()
                for k in (getattr(unit, "faction_keywords", []) or [])
                if str(k).strip()
            ]
            return kw in set(keywords + faction_keywords)

        chaos_knight_units = [u for u in list(getattr(self, "units", []) or []) if _has_keyword(u, "CHAOS KNIGHTS")]
        if not chaos_knight_units:
            return

        for unit in list(getattr(self, "units", []) or []):
            if not _has_keyword(unit, "CHAOS"):
                raise ArmyValidationError(
                    "Dreadblades: all models in the army must have the CHAOS keyword to include Chaos Knights allies."
                )

        titanic_models = 0
        war_dog_models = 0

        for unit in chaos_knight_units:
            if getattr(unit, "is_warlord", False):
                raise ArmyValidationError(
                    f"Dreadblades: Chaos Knights unit '{getattr(unit, 'name', 'Unknown')}' cannot be your Warlord."
                )
            if getattr(unit, "enhancement", None) is not None:
                raise ArmyValidationError(
                    f"Dreadblades: Chaos Knights unit '{getattr(unit, 'name', 'Unknown')}' cannot take Enhancements."
                )

            model_count = len(getattr(unit, "models", []) or [])
            if _has_keyword(unit, "TITANIC"):
                titanic_models += model_count
            elif _has_keyword(unit, "WAR DOG"):
                war_dog_models += model_count
            else:
                raise ArmyValidationError(
                    f"Dreadblades: Chaos Knights unit '{getattr(unit, 'name', 'Unknown')}' is neither TITANIC nor WAR DOG."
                )

        if titanic_models and war_dog_models:
            raise ArmyValidationError(
                "Dreadblades: cannot include both TITANIC and WAR DOG models."
            )
        if titanic_models > 1:
            raise ArmyValidationError(
                f"Dreadblades: too many TITANIC models included ({titanic_models}); maximum is 1."
            )
        if war_dog_models > 3:
            raise ArmyValidationError(
                f"Dreadblades: too many WAR DOG models included ({war_dog_models}); maximum is 3."
            )

    def _validate_freeblades(self) -> None:
        fid = str(getattr(self, "faction_id", "") or "").strip().upper()
        if fid == "QI":
            return

        def _has_keyword(unit, keyword: str) -> bool:
            if unit is None:
                return False
            fn = getattr(unit, "has_any_keyword", None)
            if callable(fn):
                return bool(fn(keyword))
            kw = (keyword or "").strip().upper()
            if not kw:
                return False
            keywords = [
                str(k).strip().upper()
                for k in (getattr(unit, "keywords", []) or [])
                if str(k).strip()
            ]
            faction_keywords = [
                str(k).strip().upper()
                for k in (getattr(unit, "faction_keywords", []) or [])
                if str(k).strip()
            ]
            return kw in set(keywords + faction_keywords)

        imperial_knight_units = [
            u for u in list(getattr(self, "units", []) or [])
            if _has_keyword(u, "IMPERIAL KNIGHTS")
        ]
        if not imperial_knight_units:
            return

        for unit in list(getattr(self, "units", []) or []):
            if not _has_keyword(unit, "IMPERIUM"):
                raise ArmyValidationError(
                    "Freeblades: all models in the army must have the IMPERIUM keyword to include Imperial Knights allies."
                )

        titanic_models = 0
        armiger_models = 0

        for unit in imperial_knight_units:
            if getattr(unit, "is_warlord", False):
                raise ArmyValidationError(
                    f"Freeblades: Imperial Knights unit '{getattr(unit, 'name', 'Unknown')}' cannot be your Warlord."
                )
            if getattr(unit, "enhancement", None) is not None:
                raise ArmyValidationError(
                    f"Freeblades: Imperial Knights unit '{getattr(unit, 'name', 'Unknown')}' cannot take Enhancements."
                )

            model_count = len(getattr(unit, "models", []) or [])
            if _has_keyword(unit, "TITANIC"):
                titanic_models += model_count
            elif _has_keyword(unit, "ARMIGER"):
                armiger_models += model_count
            else:
                raise ArmyValidationError(
                    f"Freeblades: Imperial Knights unit '{getattr(unit, 'name', 'Unknown')}' is neither TITANIC nor ARMIGER."
                )

        if titanic_models and armiger_models:
            raise ArmyValidationError("Freeblades: cannot include both TITANIC and ARMIGER models.")
        if titanic_models > 1:
            raise ArmyValidationError(
                f"Freeblades: too many TITANIC models included ({titanic_models}); maximum is 1."
            )
        if armiger_models > 3:
            raise ArmyValidationError(
                f"Freeblades: too many ARMIGER models included ({armiger_models}); maximum is 3."
            )

    def _cult_of_dark_gods_points_cap(self) -> int:
        limit = int(self.points_limit or 0)
        if limit <= 0:
            return 0
        if limit <= 1000:
            return 250
        if limit <= 2000:
            return 500
        return 750

    def validate_cult_of_dark_gods(self) -> None:
        fid = str(getattr(self, "faction_id", "") or "").strip().upper()
        if fid != "CSM":
            return

        def _norm_name(name: str) -> str:
            txt = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower())
            return re.sub(r"\s+", " ", txt).strip()

        allowed = {_norm_name(n) for n in CULT_OF_DARK_GODS_UNITS}
        cult_units = []
        for unit in list(getattr(self, "units", []) or []):
            unit_name = getattr(unit, "name", "")
            if _norm_name(unit_name) in allowed:
                cult_units.append(unit)

        if not cult_units:
            return

        csm_mgr = getattr(self, "chaos_space_marines_detachments", None)
        is_renegade_warband = bool(getattr(csm_mgr, "is_renegade_warband", lambda: False)()) if csm_mgr is not None else False
        if is_renegade_warband:
            raise ArmyValidationError(
                "Slaves to None: Renegade Warband armies cannot use the Cults of the Dark Gods rule."
            )

        for unit in cult_units:
            unit.faction_keywords = ["Heretic Astartes"]
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["cult_of_dark_gods"] = True
            if _norm_name(getattr(unit, "name", "")) == "plague marines":
                sr["infused_blessings_of_nurgle_disabled"] = True
            unit.special_rules = sr
            invalidate = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate):
                invalidate()

        cap = self._cult_of_dark_gods_points_cap()
        total = 0
        for unit in cult_units:
            total += int(unit.get_unit_cost())
        if cap <= 0 or total > cap:
            raise ArmyValidationError(
                f"Cult of the Dark Gods: cult allies total {total} points (cap {cap})."
            )

    def validate_allies(self):
        # Imperial Knights: Freeblades.
        self._validate_freeblades()
        # Imperial Agents: Assigned Agents.
        self._validate_assigned_agents()
        dru_mgr = getattr(self, "drukhari_detachments", None)
        is_reapers_wager = bool(getattr(dru_mgr, "is_reapers_wager", lambda: False)()) if dru_mgr is not None else False
        if is_reapers_wager:
            self._validate_reapers_wager_harlequins()
            self._validate_daemonic_pact()
            return
        # Drukhari: Corsairs and Travelling Players.
        if army_has_ability_id(self, ABILITY_CORSAIRS_AND_TRAVELLING_PLAYERS):
            self._validate_corsairs_and_travelling_players()
            self._validate_daemonic_pact()
            return
        # Disparate Paths: allow Harlequins/Ynnari alongside the army faction.
        if not army_has_ability_id(self, ABILITY_DISPARATE_PATHS):
            self._validate_daemonic_pact()
            return
        self._validate_disparate_paths()
        self._validate_daemonic_pact()

    def _validate_disparate_paths(self) -> None:
        """
        Disparate Paths:
        - Include HARLEQUINS units despite missing the base faction keyword.
        - Unless otherwise stated, HARLEQUINS and YNNARI cannot be selected as Army Faction.
        """
        if self._army_faction_matches_pact("HARLEQUINS") or self._army_faction_matches_pact("YNNARI"):
            raise ArmyValidationError(
                "Disparate Paths: armies cannot select 'HARLEQUINS' or 'Ynnari' as their Army Faction."
            )

        allowed = set()
        allowed.update(
            str(k).strip().upper()
            for k in (getattr(self, "faction_keyword", []) or [])
            if str(k).strip()
        )

        if not allowed:
            fid = str(getattr(self, "faction_id", "") or "").strip().upper()
            if fid == "AE":
                allowed.update({"AELDARI", "ASURYANI"})
            elif fid == "DRU":
                allowed.add("DRUKHARI")

        allowed.update({"HARLEQUINS", "YNNARI"})
        for u in list(getattr(self, "units", []) or []):
            fks = [
                str(k).strip().upper()
                for k in (getattr(u, "faction_keywords", []) or [])
                if str(k).strip()
            ]
            if not fks:
                continue
            if not any(k in allowed for k in fks):
                raise ArmyValidationError(
                    f"Unit '{getattr(u, 'name', 'Unknown')}' has faction keywords {fks}, "
                    "which are not allowed for an army with Disparate Paths (allows base faction + HARLEQUINS/YNNARI)."
                )

    def _corsairs_points_cap(self) -> int:
        limit = int(self.points_limit or 0)
        if limit <= 0:
            return 0
        if limit <= 1000:
            return 250
        if limit <= 2000:
            return 500
        return 750

    def _reapers_wager_harlequins_points_cap(self) -> int:
        limit = int(self.points_limit or 0)
        if limit <= 0:
            return 0
        if limit <= 1000:
            return 500
        if limit <= 2000:
            return 1000
        return 1500

    def _assigned_agents_unit_caps(self) -> dict[str, int]:
        limit = int(self.points_limit or 0)
        if limit <= 0:
            return {"retinue": 0, "character": 0, "requisitioned": 0}
        if limit <= 1000:
            return {"retinue": 1, "character": 1, "requisitioned": 1}
        if limit <= 2000:
            return {"retinue": 2, "character": 2, "requisitioned": 1}
        return {"retinue": 3, "character": 3, "requisitioned": 2}

    def _unit_has_any_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        kw = str(keyword or "").strip().upper()
        if not kw:
            return False
        fn = getattr(unit, "has_any_keyword", None)
        if callable(fn):
            return bool(fn(kw))
        keywords = [
            str(k).strip().upper()
            for k in (getattr(unit, "keywords", []) or [])
            if str(k).strip()
        ]
        faction_keywords = [
            str(k).strip().upper()
            for k in (getattr(unit, "faction_keywords", []) or [])
            if str(k).strip()
        ]
        return kw in set(keywords + faction_keywords)

    def _is_agents_of_imperium_unit(self, unit) -> bool:
        return self._unit_has_any_keyword(unit, "AGENTS OF THE IMPERIUM")

    def _is_voidfarers_character_unit(self, unit) -> bool:
        return self._unit_has_any_keyword(unit, "VOIDFARERS") and bool(getattr(unit, "is_character", False))

    def _is_inquisitor_unit(self, unit) -> bool:
        return self._unit_has_any_keyword(unit, "INQUISITOR")

    def _is_voidsmen_at_arms_unit(self, unit) -> bool:
        return self._unit_has_any_keyword(unit, "VOIDSMEN-AT-ARMS")

    def _is_inquisitorial_agents_unit(self, unit) -> bool:
        return self._unit_has_any_keyword(unit, "INQUISITORIAL AGENTS")

    def _validate_corsairs_and_travelling_players(self) -> None:
        allied_units = []

        def _has_keyword(unit, keyword: str) -> bool:
            if unit is None:
                return False
            fn = getattr(unit, "has_any_keyword", None)
            if callable(fn):
                return bool(fn(keyword))
            kw = (keyword or "").strip().upper()
            if not kw:
                return False
            keywords = [
                str(k).strip().upper()
                for k in (getattr(unit, "keywords", []) or [])
                if str(k).strip()
            ]
            faction_keywords = [
                str(k).strip().upper()
                for k in (getattr(unit, "faction_keywords", []) or [])
                if str(k).strip()
            ]
            return kw in set(keywords + faction_keywords)

        def _faction_keywords(unit) -> list[str]:
            return [
                str(k).strip().upper()
                for k in (getattr(unit, "faction_keywords", []) or [])
                if str(k).strip()
            ]

        for unit in list(getattr(self, "units", []) or []):
            if unit is None:
                continue
            is_dru = _has_keyword(unit, "DRUKHARI")
            is_harl = _has_keyword(unit, "HARLEQUINS")
            is_anhr = _has_keyword(unit, "ANHRATHE")

            if not (is_dru or is_harl or is_anhr):
                fks = _faction_keywords(unit)
                raise ArmyValidationError(
                    f"Unit '{getattr(unit, 'name', 'Unknown')}' has faction keywords {fks}, "
                    "which are not allowed for Corsairs and Travelling Players (allows DRUKHARI + HARLEQUINS + ANHRATHE)."
                )

            if is_harl or is_anhr:
                allied_units.append(unit)

        if not allied_units:
            return

        for unit in allied_units:
            if getattr(unit, "is_warlord", False):
                raise ArmyValidationError(
                    f"Corsairs and Travelling Players: allied unit '{getattr(unit, 'name', 'Unknown')}' cannot be your Warlord."
                )
            if getattr(unit, "enhancement", None) is not None:
                raise ArmyValidationError(
                    f"Corsairs and Travelling Players: allied unit '{getattr(unit, 'name', 'Unknown')}' cannot take Enhancements."
                )

        cap = self._corsairs_points_cap()
        total = 0
        for unit in allied_units:
            total += int(unit.get_unit_cost())
        if cap <= 0 or total > cap:
            raise ArmyValidationError(
                f"Corsairs and Travelling Players: allied units total {total} points (cap {cap})."
            )

    def _validate_reapers_wager_harlequins(self) -> None:
        harlequins_units = []
        for unit in list(getattr(self, "units", []) or []):
            if unit is None:
                continue
            is_drukhari = self._unit_has_any_keyword(unit, "DRUKHARI")
            is_harlequins = self._unit_has_any_keyword(unit, "HARLEQUINS")
            if not (is_drukhari or is_harlequins):
                fks = [
                    str(k).strip().upper()
                    for k in (getattr(unit, "faction_keywords", []) or [])
                    if str(k).strip()
                ]
                raise ArmyValidationError(
                    f"Reaper's Wager: unit '{getattr(unit, 'name', 'Unknown')}' has faction keywords {fks}, "
                    "which are not allowed (allows DRUKHARI + HARLEQUINS)."
                )
            if is_harlequins:
                harlequins_units.append(unit)

        if not harlequins_units:
            return

        for unit in harlequins_units:
            if getattr(unit, "is_warlord", False):
                raise ArmyValidationError(
                    f"Reaper's Wager: HARLEQUINS unit '{getattr(unit, 'name', 'Unknown')}' cannot be your Warlord."
                )

        cap = self._reapers_wager_harlequins_points_cap()
        total = 0
        for unit in harlequins_units:
            total += int(unit.get_unit_cost())
        if cap <= 0 or total > cap:
            raise ArmyValidationError(
                f"Reaper's Wager: HARLEQUINS units total {total} points (cap {cap})."
            )

    def _validate_assigned_agents(self) -> None:
        agents_units = [u for u in list(getattr(self, "units", []) or []) if self._is_agents_of_imperium_unit(u)]
        if not agents_units:
            return
        faction_id = str(getattr(self, "faction_id", "") or "").strip().upper()
        if faction_id == "AOI":
            return

        for unit in list(getattr(self, "units", []) or []):
            if not self._unit_has_any_keyword(unit, "IMPERIUM"):
                raise ArmyValidationError(
                    "Assigned Agents: all units must have the IMPERIUM keyword to include Agents of the Imperium allies."
                )

        retinue = 0
        character = 0
        requisitioned = 0
        voidsmen_at_arms_retinue = 0
        inquisitorial_agents_retinue = 0
        for unit in agents_units:
            if getattr(unit, "is_dedicated_transport", False):
                continue
            has_requisitioned = self._unit_has_any_keyword(unit, "REQUISITIONED")
            has_retinue = self._unit_has_any_keyword(unit, "RETINUE")
            if has_requisitioned:
                requisitioned += 1
            elif has_retinue:
                retinue += 1
                if self._is_voidsmen_at_arms_unit(unit):
                    voidsmen_at_arms_retinue += 1
                if self._is_inquisitorial_agents_unit(unit):
                    inquisitorial_agents_retinue += 1
            elif getattr(unit, "is_character", False):
                character += 1
            else:
                uname = getattr(unit, "name", "Unknown unit")
                raise ArmyValidationError(
                    f"Assigned Agents: cannot classify {uname} as Requisitioned, Retinue, or Character."
                )

        caps = self._assigned_agents_unit_caps()
        all_units = list(getattr(self, "units", []) or [])
        voidfarers_character_units = sum(
            1 for unit in all_units if self._is_voidfarers_character_unit(unit)
        )
        inquisitor_units = sum(1 for unit in all_units if self._is_inquisitor_unit(unit))
        exempt_retinue = min(voidsmen_at_arms_retinue, voidfarers_character_units) + min(
            inquisitorial_agents_retinue, inquisitor_units
        )
        retinue = max(0, retinue - exempt_retinue)
        if retinue > caps["retinue"]:
            raise ArmyValidationError(
                f"Assigned Agents: too many Retinue units ({retinue}/{caps['retinue']})."
            )
        if character > caps["character"]:
            raise ArmyValidationError(
                f"Assigned Agents: too many Character units ({character}/{caps['character']})."
            )
        if requisitioned > caps["requisitioned"]:
            raise ArmyValidationError(
                f"Assigned Agents: too many Requisitioned units ({requisitioned}/{caps['requisitioned']})."
            )

    def _daemonic_pact_points_cap(self) -> int:
        limit = int(self.points_limit or 0)
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
        fn = getattr(unit, "has_any_keyword", None)
        if callable(fn):
            return bool(fn("LEGIONES DAEMONICA"))
        kw = "LEGIONES DAEMONICA"
        keywords = [
            str(k).strip().upper()
            for k in (getattr(unit, "keywords", []) or [])
            if str(k).strip()
        ]
        faction_keywords = [
            str(k).strip().upper()
            for k in (getattr(unit, "faction_keywords", []) or [])
            if str(k).strip()
        ]
        return kw in set(keywords + faction_keywords)

    def _detachment_daemon_pact_config(self) -> dict[str, str]:
        faction_id = str(getattr(self, "faction_id", "") or "").strip().upper()
        if faction_id == "WE" and self.has_detachment_type("Khorne Daemonkin", faction_id="WE"):
            return {
                "ally_source_rule": "Pact of Blood",
                "allied_faction": "Blood Legions",
                "parent_faction": "World Eaters",
                "parent_faction_id": "WE",
                "god_keyword": "KHORNE",
            }
        if faction_id == "EC" and self.has_detachment_type("Carnival of Excess", faction_id="EC"):
            return {
                "ally_source_rule": "Pact of Excess",
                "allied_faction": "Legions of Excess",
                "parent_faction": "Emperor's Children",
                "parent_faction_id": "EC",
                "god_keyword": "SLAANESH",
            }
        return {}

    @staticmethod
    def _detachment_daemon_pact_context(unit) -> dict[str, str]:
        context: dict[str, str] = {}
        for source in (
            getattr(unit, "build_metadata", None),
            getattr(unit, "special_rules", None),
        ):
            if not isinstance(source, dict):
                continue
            nested = source.get("ally_context")
            if isinstance(nested, dict):
                for key, value in nested.items():
                    if str(value or "").strip():
                        context[str(key)] = str(value)
            for key in ("ally_source_rule", "allied_faction", "parent_faction", "parent_faction_id"):
                value = source.get(key)
                if str(value or "").strip():
                    context[key] = str(value)
        return context

    def _is_detachment_daemon_pact_unit(self, unit, config: dict[str, str]) -> bool:
        if unit is None or not config:
            return False
        context = self._detachment_daemon_pact_context(unit)
        if not context:
            return False
        for key in ("ally_source_rule", "parent_faction_id"):
            if str(context.get(key, "") or "").strip().upper() != str(config.get(key, "") or "").strip().upper():
                return False
        allied_faction = str(context.get("allied_faction", "") or "").strip().upper()
        if allied_faction and allied_faction != str(config.get("allied_faction", "") or "").strip().upper():
            return False
        parent_faction = str(context.get("parent_faction", "") or "").strip().upper()
        if parent_faction and parent_faction != str(config.get("parent_faction", "") or "").strip().upper():
            return False
        god_keyword = str(config.get("god_keyword", "") or "").strip().upper()
        return bool(god_keyword and self._unit_has_any_keyword(unit, god_keyword))

    def _validate_detachment_daemon_pact_units(self, pact_units: list, config: dict[str, str]) -> None:
        if not pact_units:
            return
        source_rule = str(config.get("ally_source_rule", "Pact") or "Pact")
        allied_faction = str(config.get("allied_faction", "daemon") or "daemon")
        for unit in pact_units:
            if getattr(unit, "is_warlord", False):
                raise ArmyValidationError(
                    f"{source_rule}: allied unit '{getattr(unit, 'name', 'Unknown')}' cannot be your Warlord."
                )
            if getattr(unit, "enhancement", None) is not None:
                raise ArmyValidationError(
                    f"{source_rule}: allied unit '{getattr(unit, 'name', 'Unknown')}' cannot take Enhancements."
                )
        cap = self._daemonic_pact_points_cap()
        total = sum(int(unit.get_unit_cost()) for unit in pact_units)
        if cap <= 0 or total > cap:
            raise ArmyValidationError(
                f"{source_rule}: {allied_faction} allies total {total} points (cap {cap})."
            )

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
        pact_config = self._detachment_daemon_pact_config()
        pact_units = [unit for unit in daemon_units if self._is_detachment_daemon_pact_unit(unit, pact_config)]
        if pact_units:
            self._validate_detachment_daemon_pact_units(pact_units, pact_config)
            daemon_units = [unit for unit in daemon_units if unit not in pact_units]
            if not daemon_units:
                return
        if faction_id not in {"CSM", "QT"}:
            raise ArmyValidationError("Daemonic Pact: LEGIONES DAEMONICA units are only allowed in Chaos Knights or Heretic Astartes armies.")

        base_keyword = "CHAOS KNIGHTS" if faction_id == "QT" else "HERETIC ASTARTES"
        for unit in list(getattr(self, "units", []) or []):
            if unit in daemon_units:
                continue
            fn = getattr(unit, "has_any_keyword", None)
            has_keyword = bool(fn(base_keyword)) if callable(fn) else False
            if not has_keyword:
                raise ArmyValidationError(
                    f"Daemonic Pact: all non-daemon units must have the {base_keyword} keyword to include daemon allies."
                )

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
            total += int(unit.get_unit_cost())
        if cap <= 0 or total > cap:
            raise ArmyValidationError(
                f"Daemonic Pact: daemon allies total {total} points (cap {cap})."
            )

        god_keywords = ("KHORNE", "TZEENTCH", "NURGLE", "SLAANESH")
        for god in god_keywords:
            with_god = []
            for unit in daemon_units:
                fn = getattr(unit, "has_any_keyword", None)
                if callable(fn) and fn(god):
                    with_god.append(unit)
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
        self.validate_unique_model_restrictions()
        self.validate_ynnari_epic_hero_restrictions()
        self.validate_tau_independent_power()
        self.validate_leaders()
        self.validate_enhancements()
        self.validate_warlord()
        self.validate_spawn_only_units()
        self.validate_daemonic_allegiances()
        self.validate_detachment_rules()
        self.validate_space_marine_chapters()
        self.validate_dreadblades()
        self.validate_cult_of_dark_gods()
        self.validate_allies()
        logger.info("Army is valid and ready for battle!")

    def get_active_units(self) -> List[Unit]:
        active = []
        for unit in list(self.units or []):
            fn = getattr(unit, "is_active_for_rules", None)
            if callable(fn):
                if fn():
                    active.append(unit)
                continue
            if bool(getattr(unit, "deployed", False)) and bool(unit.is_alive()):
                active.append(unit)
        return active

    def __str__(self):
        detachment_summary = ", ".join(self.get_detachment_types()) or self.get_primary_detachment_type()
        return f"Army: {self.faction} - {detachment_summary}\n{self.units}"

    def __eq__(self, other):
        return self._id == other._id

    def __hash__(self):
        return hash(self._id)

    def set_player(self, player) -> None:
        """Set the player that owns this army."""
        self.player = player
        self.configure_rule_managers()

    def _destroy_unit_models(self, unit: Unit, game_map=None) -> None:
        """Destroy all models in a unit (best-effort)."""
        models = list(getattr(unit, "models", []) or [])
        for model in models:
            die_fn = getattr(model, "die", None)
            if callable(die_fn):
                die_fn(game_map=game_map)
                continue
            remove_fn = getattr(unit, "remove_model", None)
            if callable(remove_fn):
                remove_fn(model, fleed=False, game_map=game_map)

    def _assigned_agents_destroy_empty_transports(self, battle_round: int, game=None) -> None:
        if int(battle_round or 0) != 1:
            return
        faction_id = str(getattr(self, "faction_id", "") or "").strip().upper()
        if faction_id == "AOI":
            return
        units = list(getattr(self, "units", []) or [])
        if not any(self._is_agents_of_imperium_unit(u) for u in units):
            return
        game_map = getattr(game, "map", None)
        for unit in units:
            if unit is None or not self._is_agents_of_imperium_unit(unit):
                continue
            if not getattr(unit, "is_dedicated_transport", False):
                continue
            alive_fn = getattr(unit, "is_alive", None)
            if not callable(alive_fn):
                raise AttributeError("Unit is missing is_alive().")
            if not alive_fn():
                continue
            if len(getattr(unit, "transport_passengers", []) or []) > 0:
                continue
            self._destroy_unit_models(unit, game_map=game_map)

    def on_prebattle_rules_start(self, *, game=None) -> None:
        """Army-level hook for setup-phase pre-battle rules (before Scout moves)."""
        if game is None:
            game = getattr(getattr(self, "player", None), "game", None)
        mgr = getattr(self, "tau_empire_detachments", None)
        if mgr is not None and hasattr(mgr, "on_prebattle_rules_start"):
            mgr.on_prebattle_rules_start(game=game)
        ia_mgr = getattr(self, "imperial_agents_detachments", None)
        if ia_mgr is not None and hasattr(ia_mgr, "on_prebattle_rules_start"):
            ia_mgr.on_prebattle_rules_start(game=game)

    def on_battle_round_start(self, battle_round: int) -> None:
        """Army-level start-of-battle-round hook for faction rules/state resets."""
        game = getattr(getattr(self, "player", None), "game", None)
        mgr = getattr(self, "blessings_of_khorne", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round))
            if game is not None and bool(getattr(game, "is_authoritative", True)):
                try:
                    from ..engine.decision_kinds import DECISION_CHOOSE_BLESSINGS
                    from ..utility.entity_ids import get_entity_id
                except Exception:
                    DECISION_CHOOSE_BLESSINGS = None
                if DECISION_CHOOSE_BLESSINGS:
                    army_id = get_entity_id(self)
                    queue = getattr(game, "decision_queue", None)
                    pending = False
                    if queue is not None and hasattr(queue, "list"):
                        for req in list(queue.list() or []):
                            if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_BLESSINGS:
                                continue
                            ctx = getattr(req, "context", {}) or {}
                            if str(ctx.get("army_id", "")) == str(army_id):
                                pending = True
                                break
                    if not pending:
                        try:
                            req = mgr.build_start_of_round_request(self, battle_round=int(battle_round), game=game)
                        except Exception:
                            req = None
                        if req is not None and hasattr(game, "request_decision"):
                            game.request_decision(req)
        mgr = getattr(self, "world_eaters_detachments", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "orks_detachments", None)
        if mgr is not None and hasattr(mgr, "on_battle_round_start"):
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "aeldari_detachments", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "battle_focus", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "templar_vows", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "shadow_form", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "wrathful_presence", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "crimson_king", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "harbingers_of_dread", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "tyranids_detachments", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "grey_knights_detachments", None)
        if mgr is not None and hasattr(mgr, "on_battle_round_start"):
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "death_guard_detachments", None)
        if mgr is not None and hasattr(mgr, "on_battle_round_start"):
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "tau_empire_detachments", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "cult_ambush", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "acts_of_faith", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "relics_of_the_matriarchs", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "doctrina_imperatives", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "adeptus_mechanicus_detachments", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "adepta_sororitas_detachments", None)
        if mgr is not None and hasattr(mgr, "on_battle_round_start"):
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "code_chivalric", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round))
        mgr = getattr(self, "imperial_knights_detachments", None)
        if mgr is not None and hasattr(mgr, "on_battle_round_start"):
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "space_marines_detachments", None)
        if mgr is not None and hasattr(mgr, "on_battle_round_start"):
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "voice_of_command", None)
        if mgr is not None:
            # Orders per officer are tracked by battle round.
            for unit in list(getattr(self, "units", []) or []):
                mgr._order_issued_state(unit, int(battle_round))
        mgr = getattr(self, "astra_militarum_detachments", None)
        if mgr is not None and hasattr(mgr, "on_battle_round_start"):
            mgr.on_battle_round_start(int(battle_round), game=game)
        mgr = getattr(self, "voice_of_triarch", None)
        if mgr is not None:
            mgr.on_battle_round_start(int(battle_round), game=game)
        self._queue_monarch_of_the_hunt(game=game, battle_round=int(battle_round))
        self._queue_piratical_raiders(game=game, battle_round=int(battle_round))
        self._queue_methodical_destruction(game=game, battle_round=int(battle_round))
        self._queue_exemplar_of_the_code(game=game, battle_round=int(battle_round))
        self._queue_prey_selection(game=game, battle_round=int(battle_round))
        self._queue_singular_purpose(game=game, battle_round=int(battle_round))
        self._queue_archons_will(game=game, battle_round=int(battle_round))
        self._queue_priority_objective_identified(game=game, battle_round=int(battle_round))
        self._assigned_agents_destroy_empty_transports(int(battle_round), game=game)

    def _eligible_quarry_units(self, enemy_units: list, *, exclude_embarked: bool = False) -> list:
        eligible = []
        seen = set()
        for enemy in list(enemy_units or []):
            if enemy is None:
                continue
            try:
                if bool(getattr(enemy, "is_attached_leader", False)):
                    continue
            except Exception:
                pass
            try:
                root = enemy.get_attached_unit_root()
            except Exception:
                root = enemy
            try:
                rid = getattr(root, "_id", None)
                if not rid or rid in seen:
                    continue
                seen.add(rid)
            except Exception:
                continue
            try:
                if not root.is_alive():
                    continue
            except Exception:
                continue
            if exclude_embarked:
                try:
                    if bool(getattr(root, "is_embarked", False)):
                        continue
                    if getattr(root, "embarked_in", None) is not None:
                        continue
                except Exception:
                    pass
            eligible.append(root)
        if not eligible:
            return []
        try:
            eligible.sort(key=lambda u: str(getattr(u, "name", "")))
        except Exception:
            pass
        return eligible

    def _build_quarry_selection_request(
        self,
        *,
        game,
        source_unit,
        enemy_units: list,
        ability_key: str,
        prompt: str,
        ability_name: Optional[str] = None,
        exclude_embarked: bool = False,
        context_extra: Optional[dict] = None,
        allow_skip: bool = False,
    ) -> Optional[object]:
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.entity_ids import get_entity_id
        except Exception:
            return None

        player = getattr(self, "player", None)
        if player is None or source_unit is None:
            return None
        queue = getattr(game, "decision_queue", None)
        source_id = None
        try:
            source_id = get_entity_id(source_unit)
        except Exception:
            source_id = None
        if queue is not None and hasattr(queue, "list") and source_id:
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("ability", "")) == str(ability_key) and str(ctx.get("source_unit_id", "")) == str(source_id):
                    return None

        eligible = self._eligible_quarry_units(enemy_units, exclude_embarked=exclude_embarked)
        if not eligible:
            return None

        options = [
            DecisionOption.create(
                str(getattr(u, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(u)},
            )
            for u in eligible
        ]
        if bool(allow_skip):
            options.append(DecisionOption.create("None", payload={"action": "skip", "skip": True}))
        if not options:
            return None
        context = {"ability": ability_key, "source_unit_id": source_id}
        if ability_name:
            context["ability_name"] = str(ability_name)
        if allow_skip:
            context["allow_skip"] = True
        if isinstance(context_extra, dict):
            context.update(context_extra)
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(player, "id", None),
            options=options,
            context=context,
        )

    def _queue_archons_will(self, *, game, battle_round: int) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if int(battle_round or 0) != 1:
            return
        player = getattr(self, "player", None)
        if player is None:
            return

        objective_pool = list(getattr(game, "objectives", []) or [])
        if not objective_pool:
            objective_pool = list(getattr(getattr(game, "map", None), "objectives", []) or [])
        objectives = []
        for objective in objective_pool:
            objective_id = str(get_entity_id(objective) or "")
            if not objective_id:
                continue
            objective_point = getattr(objective, "location", None)
            if objective_point is None or bool(getattr(objective_point, "removed", False)):
                continue
            objectives.append((objective_id, objective))
        objectives.sort(key=lambda item: str(item[0]))
        if not objectives:
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        seen_roots: set[str] = set()
        for unit in list(getattr(self, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if not root_id or root_id in seen_roots:
                continue
            seen_roots.add(root_id)
            try:
                if not root.is_alive():
                    continue
            except Exception:
                continue

            has_archons_will = False
            try:
                has_archons_will, _ = root._find_ability_with_patterns(["archon's will", "archons will"])
            except Exception:
                has_archons_will = False
            if not has_archons_will:
                continue

            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and str(sr.get("archons_will_objective_id", "") or "").strip():
                continue

            duplicate = False
            if queue is not None and hasattr(queue, "list"):
                for pending in list(queue.list() or []):
                    if str(getattr(pending, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    pending_ctx = dict(getattr(pending, "context", {}) or {})
                    if str(pending_ctx.get("ability", "") or "") != "archons_will_objective":
                        continue
                    if str(pending_ctx.get("source_unit_id", "") or "") != root_id:
                        continue
                    duplicate = True
                    break
            if duplicate:
                continue

            options = []
            for idx, (objective_id, objective) in enumerate(objectives):
                label = str(getattr(objective, "name", "") or f"Objective {idx + 1}")
                objective_point = getattr(objective, "location", None)
                try:
                    if objective_point is not None:
                        label = (
                            f"{label} "
                            f"({float(getattr(objective_point, 'x', 0.0)):.1f}, "
                            f"{float(getattr(objective_point, 'y', 0.0)):.1f})"
                        )
                except Exception:
                    pass
                options.append(DecisionOption.create(label, payload={"objective_id": objective_id}))
            if not options:
                continue

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Archon's Will: select one objective marker on the battlefield.",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "archons_will_objective",
                    "ability_name": "Archon's Will",
                    "source_unit_id": root_id,
                    "unit_id": root_id,
                    "optional": False,
                },
            )
            if hasattr(game, "request_decision"):
                game.request_decision(request)

    def has_active_priority_objective_identified_model(self) -> bool:
        seen_roots: set[str] = set()
        for unit in list(getattr(self, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if not root_id or root_id in seen_roots:
                continue
            seen_roots.add(root_id)
            if not getattr(root, "deployed", False):
                continue
            if not getattr(root, "is_alive", lambda: False)():
                continue
            if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
                continue
            if str(getattr(root, "reserve_status", "deployed") or "deployed").strip().lower() != "deployed":
                continue
            get_rule = getattr(root, "get_priority_objective_identified_rule", None)
            if callable(get_rule) and isinstance(get_rule(), dict):
                return True
        return False

    def get_priority_objective_identified_selected_objective(self, *, game=None):
        objective_id = str(getattr(self, "priority_objective_identified_objective_id", "") or "").strip()
        if not objective_id:
            return None
        objective_pool = []
        if game is not None:
            objective_pool = list(getattr(game, "objectives", []) or [])
            if not objective_pool:
                objective_pool = list(getattr(getattr(game, "map", None), "objectives", []) or [])
        for objective in list(objective_pool or []):
            if str(get_entity_id(objective) or "") == objective_id:
                return objective
        return None

    def _queue_priority_objective_identified(self, *, game, battle_round: int) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if int(battle_round or 0) != 1:
            return
        if str(getattr(self, "priority_objective_identified_objective_id", "") or "").strip():
            return
        player = getattr(self, "player", None)
        if player is None:
            return

        objective_pool = list(getattr(game, "objectives", []) or [])
        if not objective_pool:
            objective_pool = list(getattr(getattr(game, "map", None), "objectives", []) or [])
        objectives = []
        for objective in objective_pool:
            objective_id = str(get_entity_id(objective) or "")
            if not objective_id:
                continue
            objective_point = getattr(objective, "location", None)
            if objective_point is None or bool(getattr(objective_point, "removed", False)):
                continue
            objectives.append((objective_id, objective))
        objectives.sort(key=lambda item: str(item[0]))
        if not objectives:
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        army_id = str(get_entity_id(self) or "")
        if queue is not None and hasattr(queue, "list"):
            for pending in list(queue.list() or []):
                if str(getattr(pending, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                pending_ctx = dict(getattr(pending, "context", {}) or {})
                if str(pending_ctx.get("ability", "") or "") != "priority_objective_identified":
                    continue
                if str(pending_ctx.get("army_id", "") or "") != army_id:
                    continue
                return

        source_root = None
        source_rule = None
        seen_roots: set[str] = set()
        for unit in list(getattr(self, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if not root_id or root_id in seen_roots:
                continue
            seen_roots.add(root_id)
            if not getattr(root, "is_alive", lambda: False)():
                continue
            get_rule = getattr(root, "get_priority_objective_identified_rule", None)
            if not callable(get_rule):
                continue
            rule = get_rule()
            if not isinstance(rule, dict):
                continue
            source_root = root
            source_rule = rule
            break
        if source_root is None or not isinstance(source_rule, dict):
            return

        options = []
        candidate_objective_ids = []
        for idx, (objective_id, objective) in enumerate(objectives):
            label = str(getattr(objective, "name", "") or f"Objective {idx + 1}")
            objective_point = getattr(objective, "location", None)
            if objective_point is not None:
                label = (
                    f"{label} "
                    f"({float(getattr(objective_point, 'x', 0.0)):.1f}, "
                    f"{float(getattr(objective_point, 'y', 0.0)):.1f})"
                )
            options.append(DecisionOption.create(label, payload={"objective_id": objective_id}))
            candidate_objective_ids.append(objective_id)
        if not options:
            return

        ability_name = str(source_rule.get("source", "") or "Priority Objective Identified").strip()
        if not ability_name:
            ability_name = "Priority Objective Identified"
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select one objective marker on the battlefield.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "priority_objective_identified",
                "ability_name": ability_name,
                "army_id": army_id,
                "source_unit_id": str(get_entity_id(source_root) or ""),
                "unit_id": str(get_entity_id(source_root) or ""),
                "battle_round": int(battle_round or 0),
                "candidate_objective_ids": list(candidate_objective_ids),
                "optional": False,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)

    def _queue_monarch_of_the_hunt(self, *, game, battle_round: int) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if int(battle_round or 0) != 1:
            return
        player = getattr(self, "player", None)
        if player is None:
            return
        try:
            enemy_units = list(game.get_enemy_units(player))
        except Exception:
            enemy_units = []
        if not enemy_units:
            return
        for unit in list(getattr(self, "units", []) or []):
            if unit is None:
                continue
            try:
                if not unit.is_alive():
                    continue
            except Exception:
                continue
            try:
                found, _ = unit._find_ability_with_patterns(["monarch of the hunt"])
            except Exception:
                found = False
            if not found:
                continue
            if getattr(unit, "_monarch_of_the_hunt_quarry_ids", None):
                continue
            req = self._build_monarch_of_the_hunt_request(game=game, source_unit=unit, enemy_units=enemy_units)
            if req is not None and hasattr(game, "request_decision"):
                game.request_decision(req)

    def _build_monarch_of_the_hunt_request(
        self,
        *,
        game,
        source_unit,
        enemy_units: list,
        ability_name: Optional[str] = None,
    ) -> Optional[object]:
        return self._build_quarry_selection_request(
            game=game,
            source_unit=source_unit,
            enemy_units=enemy_units,
            ability_key="monarch_of_the_hunt",
            prompt="Select quarry (Monarch of the Hunt).",
            ability_name=ability_name or "Monarch of the Hunt",
            exclude_embarked=True,
        )

    def _queue_piratical_raiders(self, *, game, battle_round: int) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if int(battle_round or 0) != 1:
            return
        player = getattr(self, "player", None)
        if player is None:
            return
        try:
            enemy_units = list(game.get_enemy_units(player))
        except Exception:
            enemy_units = []
        if not enemy_units:
            return
        for unit in list(getattr(self, "units", []) or []):
            if unit is None:
                continue
            try:
                if not unit.is_alive():
                    continue
            except Exception:
                continue
            try:
                found, _ = unit._find_ability_with_patterns(["piratical raiders"])
            except Exception:
                found = False
            if not found:
                continue
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict) and sr.get("piratical_raiders_target_id"):
                continue
            req = self._build_piratical_raiders_request(game=game, source_unit=unit, enemy_units=enemy_units)
            if req is not None and hasattr(game, "request_decision"):
                game.request_decision(req)

    def _build_piratical_raiders_request(
        self,
        *,
        game,
        source_unit,
        enemy_units: list,
        ability_name: Optional[str] = None,
    ) -> Optional[object]:
        return self._build_quarry_selection_request(
            game=game,
            source_unit=source_unit,
            enemy_units=enemy_units,
            ability_key="piratical_raiders",
            prompt="Select quarry (Piratical Raiders).",
            ability_name=ability_name or "Piratical Raiders",
            exclude_embarked=False,
        )

    def _queue_methodical_destruction(self, *, game, battle_round: int) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if int(battle_round or 0) != 1:
            return
        player = getattr(self, "player", None)
        if player is None:
            return
        try:
            enemy_units = list(game.get_enemy_units(player))
        except Exception:
            enemy_units = []
        if not enemy_units:
            return
        for unit in list(getattr(self, "units", []) or []):
            if unit is None:
                continue
            try:
                if not unit.is_alive():
                    continue
            except Exception:
                continue
            try:
                rule = unit.get_victim_selection_rule()
            except Exception:
                rule = None
            if not rule:
                continue
            if getattr(unit, "_methodical_destruction_victim_ids", None):
                continue
            ability_name = str(rule.get("source", "") or "Methodical Destruction").strip() or "Methodical Destruction"
            req = self._build_methodical_destruction_request(
                game=game,
                source_unit=unit,
                enemy_units=enemy_units,
                ability_name=ability_name,
            )
            if req is not None and hasattr(game, "request_decision"):
                game.request_decision(req)

    def _build_methodical_destruction_request(
        self,
        *,
        game,
        source_unit,
        enemy_units: list,
        ability_name: Optional[str] = None,
    ) -> Optional[object]:
        label = str(ability_name or "Methodical Destruction").strip() or "Methodical Destruction"
        prompt = f"Select victim ({label})."
        return self._build_quarry_selection_request(
            game=game,
            source_unit=source_unit,
            enemy_units=enemy_units,
            ability_key="methodical_destruction",
            prompt=prompt,
            ability_name=label,
            exclude_embarked=False,
        )

    def _queue_exemplar_of_the_code(self, *, game, battle_round: int) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if int(battle_round or 0) != 1:
            return
        player = getattr(self, "player", None)
        if player is None:
            return
        try:
            enemy_units = list(game.get_enemy_units(player))
        except Exception:
            enemy_units = []
        if not enemy_units:
            return
        for unit in list(getattr(self, "units", []) or []):
            if unit is None:
                continue
            try:
                if not unit.is_alive():
                    continue
            except Exception:
                continue
            try:
                rule = unit.get_exemplar_of_the_code_rule()
            except Exception:
                rule = None
            if not rule:
                continue
            if getattr(unit, "_exemplar_of_the_code_quarry_ids", None):
                continue
            req = self._build_exemplar_of_the_code_request(
                game=game,
                source_unit=unit,
                enemy_units=enemy_units,
                rule=rule,
            )
            if req is not None and hasattr(game, "request_decision"):
                game.request_decision(req)

    def _build_exemplar_of_the_code_request(
        self,
        *,
        game,
        source_unit,
        enemy_units: list,
        rule: Optional[dict] = None,
        allow_skip: bool = False,
    ) -> Optional[object]:
        ability_name = str(rule.get("source", "") or "Exemplar of the Code").strip() if isinstance(rule, dict) else "Exemplar of the Code"
        label = ability_name or "Exemplar of the Code"
        prompt = f"Select quarry ({label})."
        context_extra = {}
        if isinstance(rule, dict):
            context_extra = {
                "exemplar_reroll_hit": bool(rule.get("reroll_hit", False)),
                "exemplar_reroll_wound": bool(rule.get("reroll_wound", True)),
                "exemplar_precision": bool(rule.get("precision", False)),
            }
        return self._build_quarry_selection_request(
            game=game,
            source_unit=source_unit,
            enemy_units=enemy_units,
            ability_key="exemplar_of_the_code",
            prompt=prompt,
            ability_name=label,
            exclude_embarked=False,
            allow_skip=bool(allow_skip),
            context_extra=context_extra,
        )

    def _queue_prey_selection(self, *, game, battle_round: int) -> None:
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if int(battle_round or 0) != 1:
            return
        player = getattr(self, "player", None)
        if player is None:
            return
        try:
            enemy_units = list(game.get_enemy_units(player))
        except Exception:
            enemy_units = []
        if not enemy_units:
            return
        queued_source_ids: set[str] = set()
        pending_source_ids: set[str] = set()
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for pending in list(queue.list() or []):
                if str(getattr(pending, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                pending_ctx = dict(getattr(pending, "context", {}) or {})
                if str(pending_ctx.get("ability", "") or "") != "prey_selection":
                    continue
                pending_source_id = str(pending_ctx.get("source_unit_id", "") or "").strip()
                if pending_source_id:
                    pending_source_ids.add(pending_source_id)
        for unit in list(getattr(self, "units", []) or []):
            if unit is None:
                continue
            try:
                if not unit.is_alive():
                    continue
            except Exception:
                continue
            try:
                rule = unit.get_prey_selection_rule()
            except Exception:
                rule = None
            if not rule:
                continue
            source_unit_id = str(rule.get("source_unit_id", "") or "").strip() if isinstance(rule, dict) else ""
            unit_id = str(get_entity_id(unit) or "").strip()
            if source_unit_id and unit_id and source_unit_id != unit_id:
                continue
            dedupe_source_id = source_unit_id or unit_id
            if dedupe_source_id and dedupe_source_id in pending_source_ids:
                continue
            if dedupe_source_id and dedupe_source_id in queued_source_ids:
                continue
            if getattr(unit, "_prey_selection_prey_ids", None):
                continue
            req = self._build_prey_selection_request(
                game=game,
                source_unit=unit,
                enemy_units=enemy_units,
                rule=rule,
            )
            if req is not None and hasattr(game, "request_decision"):
                game.request_decision(req)
                if dedupe_source_id:
                    queued_source_ids.add(dedupe_source_id)

    def _build_prey_selection_request(
        self,
        *,
        game,
        source_unit,
        enemy_units: list,
        rule: Optional[dict] = None,
    ) -> Optional[object]:
        ability_name = str(rule.get("source", "") or "Prey selection").strip() if isinstance(rule, dict) else "Prey selection"
        label = ability_name or "Prey selection"
        prompt = f"Select prey ({label})."
        context_extra = {}
        if isinstance(rule, dict):
            keyword_list: list[str] = []
            for raw in list(rule.get("keywords", []) or []):
                keyword = str(raw or "").strip().upper()
                if keyword and keyword not in keyword_list:
                    keyword_list.append(keyword)
            single_keyword = str(rule.get("keyword", "") or "").strip().upper()
            if single_keyword and single_keyword not in keyword_list:
                keyword_list.append(single_keyword)
            primary_keyword = keyword_list[0] if keyword_list else ""
            try:
                prey_hit_bonus = int(rule.get("hit_bonus", 0) or 0)
            except Exception:
                prey_hit_bonus = 0
            try:
                prey_wound_bonus = int(rule.get("wound_bonus", 0) or 0)
            except Exception:
                prey_wound_bonus = 0
            prey_source_model_id = str(rule.get("source_model_id", "") or "").strip()
            if not prey_source_model_id and (prey_hit_bonus or prey_wound_bonus):
                try:
                    get_bearer_id = getattr(source_unit, "_get_enhancement_bearer_id", None)
                    if callable(get_bearer_id):
                        prey_source_model_id = str(get_bearer_id() or "").strip()
                except Exception:
                    prey_source_model_id = ""
            context_extra = {
                "prey_reroll_hit": bool(rule.get("reroll_hit", False)),
                "prey_reroll_wound": bool(rule.get("reroll_wound", False)),
                "prey_hit_bonus": int(prey_hit_bonus),
                "prey_wound_bonus": int(prey_wound_bonus),
                "prey_melee_only": bool(rule.get("melee_only", False)),
                "prey_keyword": primary_keyword,
                "prey_keywords": list(keyword_list),
                "prey_repick_on_destroyed": bool(rule.get("repick_on_destroyed", False)),
                "prey_source_model_id": prey_source_model_id,
            }
        return self._build_quarry_selection_request(
            game=game,
            source_unit=source_unit,
            enemy_units=enemy_units,
            ability_key="prey_selection",
            prompt=prompt,
            ability_name=label,
            exclude_embarked=False,
            context_extra=context_extra,
        )

    def _queue_singular_purpose(self, *, game, battle_round: int) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if int(battle_round or 0) != 1:
            return
        player = getattr(self, "player", None)
        if player is None:
            return
        try:
            enemy_units = list(game.get_enemy_units(player))
        except Exception:
            enemy_units = []

        objective_pool = list(getattr(game, "objectives", []) or [])
        if not objective_pool:
            objective_pool = list(getattr(getattr(game, "map", None), "objectives", []) or [])
        objectives = []
        for objective in objective_pool:
            objective_id = str(get_entity_id(objective) or "")
            if not objective_id:
                continue
            objective_point = getattr(objective, "location", None)
            if objective_point is None or bool(getattr(objective_point, "removed", False)):
                continue
            objectives.append((objective_id, objective))
        objectives.sort(key=lambda item: str(item[0]))

        if not enemy_units and not objectives:
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        seen_roots: set[str] = set()
        for unit in list(getattr(self, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if not root_id or root_id in seen_roots:
                continue
            seen_roots.add(root_id)
            try:
                if not root.is_alive():
                    continue
            except Exception:
                continue

            try:
                rule = root.get_singular_purpose_rule()
            except Exception:
                rule = None
            if not isinstance(rule, dict):
                continue

            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict):
                mode = str(sr.get("singular_purpose_mode", "") or "").strip()
                if mode:
                    continue

            duplicate = False
            if queue is not None and hasattr(queue, "list"):
                for pending in list(queue.list() or []):
                    if str(getattr(pending, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    pending_ctx = dict(getattr(pending, "context", {}) or {})
                    if str(pending_ctx.get("ability", "") or "") != "singular_purpose":
                        continue
                    if str(pending_ctx.get("source_unit_id", "") or "") != root_id:
                        continue
                    duplicate = True
                    break
            if duplicate:
                continue

            options = []
            eligible_targets = self._eligible_quarry_units(enemy_units, exclude_embarked=False)
            eligible_targets.sort(key=lambda target: str(get_entity_id(target) or ""))
            for enemy in list(eligible_targets or []):
                enemy_id = str(get_entity_id(enemy) or "")
                if not enemy_id:
                    continue
                enemy_name = str(getattr(enemy, "name", "Enemy unit") or "Enemy unit")
                options.append(
                    DecisionOption.create(
                        f"Enemy: {enemy_name}",
                        payload={"mode": "enemy_unit", "target_unit_id": enemy_id},
                    )
                )

            for idx, (objective_id, objective) in enumerate(objectives):
                label = str(getattr(objective, "name", "") or f"Objective {idx + 1}")
                objective_point = getattr(objective, "location", None)
                try:
                    if objective_point is not None:
                        label = (
                            f"{label} "
                            f"({float(getattr(objective_point, 'x', 0.0)):.1f}, "
                            f"{float(getattr(objective_point, 'y', 0.0)):.1f})"
                        )
                except Exception:
                    pass
                options.append(
                    DecisionOption.create(
                        f"Objective: {label}",
                        payload={"mode": "objective_marker", "objective_id": objective_id},
                    )
                )

            if not options:
                continue

            source_model_id = ""
            try:
                source_models = list(root.get_models_for_collision() or [])
            except Exception:
                source_models = list(getattr(root, "models", []) or [])
            for model in list(source_models or []):
                if model is None:
                    continue
                try:
                    if not bool(getattr(model, "is_alive", True)):
                        continue
                except Exception:
                    pass
                source_model_id = str(get_entity_id(model) or "")
                if source_model_id:
                    break
            if not source_model_id and source_models:
                source_model_id = str(get_entity_id(source_models[0]) or "")

            ability_name = str(rule.get("source", "") or "Singular Purpose").strip() or "Singular Purpose"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select one enemy unit or one objective marker.",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "singular_purpose",
                    "ability_name": ability_name,
                    "source_unit_id": root_id,
                    "unit_id": root_id,
                    "source_model_id": source_model_id,
                    "singular_purpose_reroll_hit": bool(rule.get("reroll_hit", False)),
                    "singular_purpose_reroll_wound": bool(rule.get("reroll_wound", False)),
                    "singular_purpose_objective_fnp": int(rule.get("objective_feel_no_pain", 5) or 5),
                    "singular_purpose_objective_oc": int(rule.get("objective_control", 15) or 15),
                    "optional": False,
                },
            )
            if hasattr(game, "request_decision"):
                game.request_decision(request)

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
            found, _ = u._find_ability_with_patterns(["reborn in blood"])
            if found:
                target = u
                break
        if target is None:
            return False

        # If already alive/on battlefield, do nothing.
        if target.is_alive():
            return False

        # Re-add the last removed model if needed (single-model unit likely has models_lost populated).
        if len(getattr(target, "models", []) or []) == 0:
            lost = list(getattr(target, "models_lost", []) or [])
            if not lost:
                return False
            m = lost[-1]
            target.models.append(m)
            m.set_parent_unit(target)

        # Restore to 8 wounds remaining
        m = target.models[0]
        if hasattr(m, "_wounds"):
            setattr(m, "_wounds", 8)
        elif hasattr(m, "wounds"):
            setattr(m, "wounds", 8)
        else:
            raise AttributeError("Model does not expose a wounds attribute.")

        # Put into standard reserves so it can arrive via Deep Strike rules.
        target.reserve_status = "reserves"
        target.deployed = True
        target.reserve_turn_deployed = None
        target.arrived_from_reserves_this_turn = False
        setattr(target, "_reborn_in_blood_pending", True)
        turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        setattr(target, "_reborn_in_blood_arrival_round", int(turn))

        # Ensure not on the map until placed
        if game is not None and hasattr(game, "map") and hasattr(game.map, "units"):
            if target in game.map.units:
                game.map.units.remove(target)

        return True

def parse_army_list(file_path: str, waha_helper: WahaHelper) -> Army:
    from .army_parse import parse_army_list as _parse_army_list

    return _parse_army_list(file_path, waha_helper)


def parse_army_list_text(list_text: str, waha_helper: WahaHelper, *, list_name: str = "army_list") -> Army:
    from .army_parse import parse_army_list_text as _parse_army_list_text

    return _parse_army_list_text(list_text, waha_helper, list_name=list_name)


def add_unit_to_army(
    army: Army,
    unit: Unit,
    model_count: int,
    wargear_dict: Dict[str, Set[Tuple[str, int]]],
    enhancement: Enhancement,
    waha_helper: WahaHelper,
    is_warlord: bool,
    *,
    build_entry_id: str | None = None,
):
    from .army_parse import add_unit_to_army as _add_unit_to_army

    return _add_unit_to_army(
        army,
        unit,
        model_count,
        wargear_dict,
        enhancement,
        waha_helper,
        is_warlord,
        build_entry_id=build_entry_id,
    )


# Example usage:
if __name__ == "__main__":
    waha_helper = WahaHelper()
    army = parse_army_list("army_lists/warhammer_app_dump.txt", waha_helper)
    logger.info(f"Parsed army: {army.faction_keyword} - {army.get_primary_detachment_type()}")
    logger.info(f"Total points: {army.get_total_points()} out of {army.points_limit}")
    logger.info(f"Number of units: {len(army.units)}")
    for unit in army.units:
        logger.info(f"- {unit.name} ({unit.get_unit_cost()} points)")
        for model in unit.models:
            logger.info(f"  - {model.name} {'(Warlord)' if unit.is_warlord else ''}")
            for wargear in model.wargear:
                if wargear:
                    logger.info(f"    - {wargear.name}")
            if hasattr(model, 'optional_wargear'):
                for wargear_option in model.optional_wargear:
                    logger.info(f"    - {model.get_optional_wargear_by_name(wargear_option).name}")
            for ability in model.abilities.keys():
                if ability:
                    logger.info(f"    - {ability} (Ability Wargear)")
            if unit.enhancement:
                logger.info(f"    - Enhancement: {unit.enhancement.name}")
    army.validate()
