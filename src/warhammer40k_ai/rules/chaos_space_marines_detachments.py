from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from ..utility.entity_ids import get_entity_id
from ..utility.dice import get_roll
from .detachment_manager import DetachmentManagerBase


@dataclass(frozen=True)
class ExperimentalAugmentation:
    key: str
    name: str
    summary: str
    roll: int


CHOLINERGIC_ACCELERANTS = ExperimentalAugmentation(
    key="CHOLINERGIC_ACCELERANTS",
    name="Cholinergic Accelerants",
    summary="Add 1 to the Attacks characteristic of melee weapons equipped by this model.",
    roll=1,
)
HYPERADRENAL_INFUSION = ExperimentalAugmentation(
    key="HYPERADRENAL_INFUSION",
    name="Hyperadrenal Infusion",
    summary="Add 2\" to the Move characteristic of this model.",
    roll=2,
)
PARANEURAL_REACTIONS = ExperimentalAugmentation(
    key="PARANEURAL_REACTIONS",
    name="Paraneural Reactions",
    summary="Improve Weapon Skill of melee weapons equipped by this model by 1.",
    roll=3,
)
SUPRACUTANEOUS_CHITINATION = ExperimentalAugmentation(
    key="SUPRACUTANEOUS_CHITINATION",
    name="Supracutaneous Chitination",
    summary="Improve the Toughness characteristic of this model by 1.",
    roll=4,
)
MACROTENSILE_SINEWS = ExperimentalAugmentation(
    key="MACROTENSILE_SINEWS",
    name="Macrotensile Sinews",
    summary="Add 1 to the Strength characteristic of melee weapons equipped by this model.",
    roll=5,
)
OPHTHALMIC_ENHANCEMENT = ExperimentalAugmentation(
    key="OPHTHALMIC_ENHANCEMENT",
    name="Ophthalmic Enhancement",
    summary="Improve Ballistic Skill of ranged weapons equipped by this model by 1.",
    roll=6,
)

EXPERIMENTAL_AUGMENTATIONS: tuple[ExperimentalAugmentation, ...] = (
    CHOLINERGIC_ACCELERANTS,
    HYPERADRENAL_INFUSION,
    PARANEURAL_REACTIONS,
    SUPRACUTANEOUS_CHITINATION,
    MACROTENSILE_SINEWS,
    OPHTHALMIC_ENHANCEMENT,
)
EXPERIMENTAL_AUGMENTATION_BY_KEY = {a.key: a for a in EXPERIMENTAL_AUGMENTATIONS}
EXPERIMENTAL_AUGMENTATION_BY_ROLL = {a.roll: a for a in EXPERIMENTAL_AUGMENTATIONS}


class ChaosSpaceMarinesDetachmentManager(DetachmentManagerBase):
    faction_id = "CSM"

    DETACHMENT_CABAL_OF_CHAOS = "Cabal of Chaos"
    DETACHMENT_CHAOS_CULT = "Chaos Cult"
    DETACHMENT_CREATIONS_OF_BILE = "Creations of Bile"
    DETACHMENT_CULT_OF_THE_ARKIFANE = "Cult of the Arkifane"
    DETACHMENT_DECEPTORS = "Deceptors"
    DETACHMENT_DREAD_TALONS = "Dread Talons"
    DETACHMENT_FELLHAMMER_SIEGE_HOST = "Fellhammer Siege-host"
    DETACHMENT_HURONS_MARAUDERS = "Huron's Marauders"
    DETACHMENT_NIGHTMARE_HUNT = "Nightmare Hunt"
    DETACHMENT_PACTBOUND_ZEALOTS = "Pactbound Zealots"
    DETACHMENT_RENEGADE_RAIDERS = "Renegade Raiders"
    DETACHMENT_RENEGADE_WARBAND = "Renegade Warband"
    DETACHMENT_SOULFORGED_WARPACK = "Soulforged Warpack"
    DETACHMENT_VETERANS_OF_THE_LONG_WAR = "Veterans of the Long War"
    _MASTERS_OF_MISDIRECTION_SELECTION_ABILITY = "deceptors_masters_of_misdirection_selection"
    _MASTERS_OF_MISDIRECTION_SOURCE = "Masters of Misdirection"
    _DECEPTORS_FALSEHOOD_DECLARE_ABILITY = "deceptors_falsehood_declare_reserves"
    _DECEPTORS_FALSEHOOD_REINFORCEMENTS_ABILITY = "deceptors_falsehood_reinforcements"
    _DECEPTORS_FALSEHOOD_SOURCE = "Falsehood"
    _DECEPTORS_SOUL_LINK_ABILITY = "deceptors_soul_link_target"
    _DECEPTORS_SOUL_LINK_SOURCE = "Soul Link"
    _DECEPTORS_COILS_OF_DECEPTION_PREFIX = "deceptors_coils_of_deception"
    _DECEPTORS_COILS_OF_DECEPTION_SOURCE = "Coils of Deception"
    _DECEPTORS_FROM_ALL_SIDES_PREFIX = "deceptors_from_all_sides"
    _DECEPTORS_FROM_ALL_SIDES_SOURCE = "From All Sides"
    _DECEPTORS_PICK_THEM_OFF_PREFIX = "deceptors_pick_them_off"
    _DECEPTORS_PICK_THEM_OFF_SOURCE = "Pick Them Off"
    _DECEPTORS_SCRAMBLED_COORDINATES_PREFIX = "deceptors_scrambled_coordinates"
    _DECEPTORS_SCRAMBLED_COORDINATES_SOURCE = "Scrambled Coordinates"
    _DREAD_TALONS_DEPTHLESS_CRUELTY_PREFIX = "dread_talons_depthless_cruelty"
    _DREAD_TALONS_DEPTHLESS_CRUELTY_SOURCE = "Depthless Cruelty"
    _DREAD_TALONS_PITILESS_HUNTERS_PREFIX = "dread_talons_pitiless_hunters"
    _DREAD_TALONS_PITILESS_HUNTERS_SOURCE = "Pitiless Hunters"
    _DREAD_TALONS_RELENTLESS_TERROR_PREFIX = "dread_talons_relentless_terror"
    _DREAD_TALONS_RELENTLESS_TERROR_SOURCE = "Relentless Terror"
    _DREAD_TALONS_SCREAMING_DESCENT_PREFIX = "dread_talons_screaming_descent"
    _DREAD_TALONS_SCREAMING_DESCENT_SOURCE = "Screaming Descent"
    _FELLHAMMER_BRUTAL_ATTRITION_PREFIX = "fellhammer_brutal_attrition"
    _FELLHAMMER_BRUTAL_ATTRITION_SOURCE = "Brutal Attrition"
    _FELLHAMMER_PERSISTENT_ASSAILANTS_PREFIX = "fellhammer_persistent_assailants"
    _FELLHAMMER_PERSISTENT_ASSAILANTS_SOURCE = "Persistent Assailants"
    _FELLHAMMER_PITILESS_CANNONADE_PREFIX = "fellhammer_pitiless_cannonade"
    _FELLHAMMER_PITILESS_CANNONADE_SOURCE = "Pitiless Cannonade"
    _FELLHAMMER_POINT_BLANK_DESTRUCTION_PREFIX = "fellhammer_point_blank_destruction"
    _FELLHAMMER_POINT_BLANK_DESTRUCTION_SOURCE = "Point-Blank Destruction"
    _FELLHAMMER_SIEGECRAFT_PREFIX = "fellhammer_siegecraft"
    _FELLHAMMER_SIEGECRAFT_SOURCE = "Siegecraft"
    _FELLHAMMER_STEADFAST_DETERMINATION_PREFIX = "fellhammer_steadfast_determination"
    _FELLHAMMER_STEADFAST_DETERMINATION_SOURCE = "Steadfast Determination"
    _HURONS_MARAUDERS_AT_THE_TYRANTS_COMMAND_PREFIX = "hurons_marauders_at_the_tyrants_command"
    _HURONS_MARAUDERS_AT_THE_TYRANTS_COMMAND_SOURCE = "At the Tyrant's Command"
    _HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX = "hurons_marauders_hardened_killers"
    _HURONS_MARAUDERS_HARDENED_KILLERS_SOURCE = "Hardened Killers"
    _HURONS_MARAUDERS_REAVERS_FLURRY_PREFIX = "hurons_marauders_reavers_flurry"
    _HURONS_MARAUDERS_REAVERS_FLURRY_SOURCE = "Reavers' Flurry"
    _NIGHTMARE_HUNT_MALICIOUS_SURGE_PREFIX = "nightmare_hunt_malicious_surge"
    _NIGHTMARE_HUNT_MALICIOUS_SURGE_SOURCE = "Malicious Surge"
    _NIGHTMARE_HUNT_PREY_ON_THE_WEAK_PREFIX = "nightmare_hunt_prey_on_the_weak"
    _NIGHTMARE_HUNT_PREY_ON_THE_WEAK_SOURCE = "Prey on the Weak"
    _NIGHTMARE_HUNT_RELENTLESS_TERROR_PREFIX = "nightmare_hunt_relentless_terror"
    _NIGHTMARE_HUNT_RELENTLESS_TERROR_SOURCE = "Relentless Terror"
    _NIGHTMARE_HUNT_TALONS_SUNK_DEEP_PREFIX = "nightmare_hunt_talons_sunk_deep"
    _NIGHTMARE_HUNT_TALONS_SUNK_DEEP_SOURCE = "Talons Sunk Deep"
    _HARDENED_KILLERS_ABILITY = "hurons_marauders_hardened_killers_choice"
    _HARDENED_KILLERS_CHOICE_BALLISTIC_SKILL = "BALLISTIC_SKILL"
    _HARDENED_KILLERS_CHOICE_RAPID_FIRE = "RAPID_FIRE"
    _HARDENED_KILLERS_CHOICE_SAVE = "SAVE"
    _TYRANNICAL_MOTIVATION_ABILITY = "tyrannical_motivation_choice"
    _TYRANNICAL_MOTIVATION_SOURCE = "Tyrannical Motivation"
    _TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE = "HURONS_ELITE"
    _TYRANNICAL_MOTIVATION_CHOICE_MOBILE_MARAUDERS = "MOBILE_MARAUDERS"
    _RENEGADE_WARBAND_VENDETTA_ABILITY = "renegade_warband_vendetta_target"
    _RENEGADE_WARBAND_VENDETTA_SOURCE = "Vendetta"
    _RENEGADE_WARBAND_WEAPONISED_HATRED_ABILITY = "renegade_warband_weaponised_hatred_target"
    _RENEGADE_WARBAND_WEAPONISED_HATRED_SOURCE = "Weaponised Hatred"
    _RENEGADE_WARBAND_TWISTED_DOCTRINE_ABILITY = "renegade_warband_twisted_doctrine"
    _RENEGADE_WARBAND_TWISTED_DOCTRINE_SOURCE = "Twisted Doctrine"
    _RENEGADE_WARBAND_TWISTED_DOCTRINE_FALL_BACK_CHOICE = "FALL_BACK_SHOOT_AND_CHARGE"
    _RENEGADE_WARBAND_TWISTED_DOCTRINE_ADVANCE_CHOICE = "ADVANCE_CHARGE"
    _RENEGADE_WARBAND_CORRUPTED_MUNITIONS_PREFIX = "renegade_warband_corrupted_munitions"
    _RENEGADE_WARBAND_CORRUPTED_MUNITIONS_SOURCE = "Corrupted Munitions"
    _RENEGADE_WARBAND_VENGEFUL_DESTRUCTION_PREFIX = "renegade_warband_vengeful_destruction"
    _RENEGADE_WARBAND_VENGEFUL_DESTRUCTION_SOURCE = "Vengeful Destruction"
    _RENEGADE_WARBAND_UNDYING_HATRED_SOURCE = "Undying Hatred"
    _RENEGADE_RAIDERS_DESPOTS_CLAIM_SOURCE = "Despot's Claim"
    _RENEGADE_RAIDERS_DREAD_REAVER_SOURCE = "Dread Reaver"
    _RENEGADE_RAIDERS_MARK_OF_THE_HOUND_SOURCE = "Mark of the Hound"
    _RENEGADE_RAIDERS_OPPORTUNISTIC_RAIDERS_SOURCE = "Opportunistic Raiders"
    _RENEGADE_RAIDERS_REAVERS_HASTE_PREFIX = "renegade_raiders_reavers_haste"
    _RENEGADE_RAIDERS_REAVERS_HASTE_SOURCE = "Reavers' Haste"
    _RENEGADE_RAIDERS_RUINOUS_RAID_PREFIX = "renegade_raiders_ruinous_raid"
    _RENEGADE_RAIDERS_RUINOUS_RAID_SOURCE = "Ruinous Raid"
    _RENEGADE_RAIDERS_SCOUR_AND_SEIZE_PREFIX = "renegade_raiders_scour_and_seize"
    _RENEGADE_RAIDERS_SCOUR_AND_SEIZE_SOURCE = "Scour and Seize"
    _RENEGADE_RAIDERS_TYRANTS_LASH_SOURCE = "Tyrant's Lash"
    _RENEGADE_RAIDERS_UNFAILINGLY_OBDURATE_SOURCE = "Unfailingly Obdurate"
    _RENEGADE_RAIDERS_WARPCHARGED_ENGINES_SOURCE = "Warpcharged Engines"
    _RENEGADE_WARBAND_EYES_OF_THE_HUNTER_SOURCE = "Eyes of the Hunter"
    _RENEGADE_WARBAND_FRATRICIDAL_TROPHIES_SOURCE = "Fratricidal Trophies"
    _RENEGADE_WARBAND_EMPYRIC_SYMBIOTE_SOURCE = "Empyric Symbiote"
    _VETERANS_OF_THE_LONG_WAR_FOCUS_ABILITY = "veterans_of_the_long_war_focus_of_hatred_target"
    _VETERANS_OF_THE_LONG_WAR_FOCUS_SOURCE = "Focus of Hatred"
    _VETERANS_OF_THE_LONG_WAR_ENDLESS_IRE_ABILITY = "veterans_endless_ire_focus_target"
    _VETERANS_BLACK_CRUSADE_PREFIX = "veterans_black_crusade"
    _VETERANS_BLACK_CRUSADE_SOURCE = "Black Crusade"
    _VETERANS_BLACK_CRUSADE_DAMAGE_KEY = "veterans_black_crusade_wounds_inflicted"
    _VETERANS_BLACK_CRUSADE_DAMAGE_CAP_KEY = "veterans_black_crusade_wounds_cap"
    _VETERANS_BRINGERS_OF_DESPAIR_PREFIX = "veterans_bringers_of_despair"
    _VETERANS_BRINGERS_OF_DESPAIR_SOURCE = "Bringers of Despair"
    _VETERANS_CONTEMPTUOUS_DISREGARD_SOURCE = "Contemptuous Disregard"
    _VETERANS_ENDLESS_IRE_SOURCE = "Endless Ire"
    _VETERANS_LET_THE_GALAXY_BURN_PREFIX = "veterans_let_the_galaxy_burn"
    _VETERANS_LET_THE_GALAXY_BURN_SOURCE = "Let the Galaxy Burn"
    _VETERANS_MILLENNIA_OF_EXPERIENCE_SOURCE = "Millennia of Experience"
    _SOULFORGED_WARPACK_FORGES_BLESSING_ABILITY = "soulforged_warpack_forges_blessing_target"
    _SOULFORGED_WARPACK_FORGES_BLESSING_SOURCE = "Forge's Blessing"
    _SOULFORGED_WARPACK_TEMPTING_ADDENDUM_SOURCE = "Tempting Addendum"
    _SOULFORGED_WARPACK_SOUL_HARVESTER_SOURCE = "Soul Harvester"
    _SOULFORGED_WARPACK_CONTRACT_SOURCE = "Debt to the Soul Forge"
    _SOULFORGED_WARPACK_DAEMONIC_POSSESION_SOURCE = "Daemonic Posession"
    _SOULFORGED_WARPACK_DESPERATE_PLEDGE_PREFIX = "soulforged_warpack_desperate_pledge"
    _SOULFORGED_WARPACK_DESPERATE_PLEDGE_SOURCE = "Desperate Pledge"
    _SOULFORGED_WARPACK_GLUT_OF_SOULS_PREFIX = "soulforged_warpack_glut_of_souls"
    _SOULFORGED_WARPACK_GLUT_OF_SOULS_SOURCE = "Glut of Souls"
    _SOULFORGED_WARPACK_CONTRACT_ACTIVE_KEY = "soulforged_warpack_contract_active"
    _SOULFORGED_WARPACK_CONTRACT_EXPIRES_PHASE_KEY = "soulforged_warpack_contract_expires_phase"
    _SOULFORGED_WARPACK_CONTRACT_TURN_KEY = "soulforged_warpack_contract_turn"
    _SOULFORGED_WARPACK_CONTRACT_OWNER_KEY = "soulforged_warpack_contract_turn_owner"
    _SOULFORGED_WARPACK_CONTRACT_SOURCE_KEY = "soulforged_warpack_contract_source"
    _SOULFORGED_WARPACK_CONTRACT_CHOICE_KEY = "soulforged_warpack_contract_choice"
    _SOULFORGED_WARPACK_DARK_PACT_TEST_MODIFIER_KEY = "soulforged_warpack_dark_pact_test_modifier"
    _SOULFORGED_WARPACK_DARK_PACT_TEST_MODIFIER_SOURCE_KEY = (
        "soulforged_warpack_dark_pact_test_modifier_source"
    )
    _SOULFORGED_WARPACK_TEMPTING_ADDENDUM_ACTIVE_KEY = "soulforged_warpack_tempting_addendum_active"
    _SOULFORGED_WARPACK_TEMPTING_ADDENDUM_EXPIRES_PHASE_KEY = "soulforged_warpack_tempting_addendum_expires_phase"
    _SOULFORGED_WARPACK_TEMPTING_ADDENDUM_TURN_KEY = "soulforged_warpack_tempting_addendum_turn"
    _SOULFORGED_WARPACK_TEMPTING_ADDENDUM_OWNER_KEY = "soulforged_warpack_tempting_addendum_turn_owner"
    _SOULFORGED_WARPACK_TEMPTING_ADDENDUM_SOURCE_KEY = "soulforged_warpack_tempting_addendum_source"
    _CULT_OF_THE_ARKIFANE_SOUL_FORGE_SOURCE = "Soul Forge Boons"
    _PACTBOUND_MARKS = ("KHORNE", "TZEENTCH", "NURGLE", "SLAANESH", "CHAOS UNDIVIDED")
    _PACTBOUND_MARK_SOURCE = "Marks of Chaos"
    _PACTBOUND_EYE_OF_TZEENTCH_SOURCE = "Eye of Tzeentch"
    _PACTBOUND_ETERNAL_HATE_PREFIX = "pactbound_eternal_hate"
    _PACTBOUND_ETERNAL_HATE_SOURCE = "Eternal Hate"
    _PACTBOUND_EYE_OF_THE_GODS_SOURCE = "Eye of the Gods"
    _PACTBOUND_EYE_OF_THE_GODS_MODEL_BONUS_KEY = "pactbound_eye_of_the_gods_model_bonuses"
    _PACTBOUND_FESTERING_MIASMA_PREFIX = "pactbound_festering_miasma"
    _PACTBOUND_FESTERING_MIASMA_SOURCE = "Festering Miasma"
    _PACTBOUND_PROFANE_ZEAL_PREFIX = "pactbound_profane_zeal"
    _PACTBOUND_PROFANE_ZEAL_SOURCE = "Profane Zeal"
    _PACTBOUND_TALISMAN_OF_BURNING_BLOOD_SOURCE = "Talisman of Burning Blood"
    _PACTBOUND_TALISMAN_DARK_PACT_BONUS_KEY = "enhancement_talisman_of_burning_blood_dark_pact_bonus"
    _PACTBOUND_TALISMAN_DARK_PACT_EXPIRES_PHASE_KEY = "enhancement_talisman_of_burning_blood_dark_pact_expires_phase"
    _PACTBOUND_TALISMAN_DARK_PACT_TURN_KEY = "enhancement_talisman_of_burning_blood_dark_pact_turn"
    _PACTBOUND_TALISMAN_DARK_PACT_OWNER_KEY = "enhancement_talisman_of_burning_blood_dark_pact_owner"
    _PACTBOUND_TORPEFYING_REFRAIN_PREFIX = "pactbound_torpefying_refrain"
    _PACTBOUND_TORPEFYING_REFRAIN_SOURCE = "Torpefying Refrain"
    _DESPERATE_DEVOTION_ALLOWED_ACTIONS = {"move", "advance", "charge"}
    _CHAOS_CULT_CHOSEN_FOR_GLORY_PREFIX = "chaos_cult_chosen_for_glory"
    _CHAOS_CULT_CHOSEN_FOR_GLORY_SOURCE = "Chosen for Glory"
    _CHAOS_CULT_CRAZED_FOCUS_PREFIX = "chaos_cult_crazed_focus"
    _CHAOS_CULT_CRAZED_FOCUS_SOURCE = "Crazed Focus"
    _CHAOS_CULT_INFERNAL_SACRIFICE_PREFIX = "chaos_cult_infernal_sacrifice"
    _CHAOS_CULT_INFERNAL_SACRIFICE_SOURCE = "Infernal Sacrifice"
    _CHAOS_CULT_SELFLESS_DEMISE_PREFIX = "chaos_cult_selfless_demise"
    _CHAOS_CULT_SELFLESS_DEMISE_SOURCE = "Selfless Demise"
    _CHAOS_CULT_MORTAL_THRALLS_PREFIX = "chaos_cult_mortal_thralls"
    _CHAOS_CULT_MORTAL_THRALLS_SOURCE = "Mortal Thralls"
    _CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX = "creations_of_bile_delayed_mutations"
    _CREATIONS_OF_BILE_DELAYED_MUTATIONS_SOURCE = "Delayed Mutations"
    _CREATIONS_OF_BILE_MASTERS_ARE_WATCHING_PREFIX = "creations_of_bile_masters_are_watching"
    _CREATIONS_OF_BILE_MASTERS_ARE_WATCHING_SOURCE = "Masters Are Watching"
    _CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX = "creations_of_bile_specimens_for_the_spider"
    _CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_SOURCE = "Specimens for the Spider"
    _EXPERIMENTAL_AUGMENTATION_REROLL_MODES = {"keep", "reroll_first", "reroll_second", "reroll_both"}
    _TWISTED_DOCTRINE_ALLOWED_ACTIONS = {"move", "advance", "fall_back", "set_up"}

    def __init__(self, army=None):
        super().__init__(army)
        self.experimental_augmentations_active_keys: set[str] = set()
        self.experimental_augmentations_selected: bool = False
        self.experimental_augmentations_selected_round: Optional[int] = None
        self.experimental_augmentations_selection_mode: str = ""
        self.experimental_augmentations_rolls: list[int] = []
        self.experimental_augmentations_pending_rolls: list[int] = []
        self.experimental_augmentations_pending_round: Optional[int] = None
        self._masters_of_misdirection_selection_resolved: bool = False
        self.masters_of_misdirection_selected_unit_ids: set[str] = set()
        self.tyrannical_motivation_choice_key: str = ""
        self._tyrannical_motivation_phase_signature: tuple[str, int, str] | None = None
        self._tyrannical_motivation_phase_hit_bonus_unit_ids: set[str] = set()
        self._tyrannical_motivation_phase_mobile_unit_ids: set[str] = set()
        self.renegade_warband_vendetta_target_unit_id: str = ""
        self.renegade_warband_weaponised_hatred_target_unit_id: str = ""
        self._renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id: str = ""
        self._renegade_warband_weaponised_hatred_last_used_battle_round: int = 0
        self.veterans_focus_of_hatred_target_unit_id: str = ""

    def is_cabal_of_chaos(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_CABAL_OF_CHAOS)

    def is_chaos_cult(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_CHAOS_CULT)

    def is_creations_of_bile(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_CREATIONS_OF_BILE)

    def is_cult_of_the_arkifane(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_CULT_OF_THE_ARKIFANE)

    def is_deceptors(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_DECEPTORS)

    def is_dread_talons(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_DREAD_TALONS)

    def is_fellhammer_siege_host(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_FELLHAMMER_SIEGE_HOST)

    def is_hurons_marauders(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_HURONS_MARAUDERS)

    def is_nightmare_hunt(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_NIGHTMARE_HUNT)

    def is_pactbound_zealots(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_PACTBOUND_ZEALOTS)

    def is_renegade_raiders(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_RENEGADE_RAIDERS)

    def is_renegade_warband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_RENEGADE_WARBAND)

    def is_soulforged_warpack(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_SOULFORGED_WARPACK)

    def is_veterans_of_the_long_war(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_VETERANS_OF_THE_LONG_WAR)

    @staticmethod
    def _unit_root(unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
            if root is not None:
                return root
        return unit

    @staticmethod
    def _unit_root_key(unit) -> str:
        root = ChaosSpaceMarinesDetachmentManager._unit_root(unit)
        if root is None:
            return ""
        unit_id = str(getattr(root, "_id", "") or "").strip()
        if unit_id:
            return unit_id
        return str(id(root))

    @staticmethod
    def _unit_entity_key(unit) -> str:
        root = ChaosSpaceMarinesDetachmentManager._unit_root(unit)
        if root is None:
            return ""
        entity_id = str(get_entity_id(root) or "").strip()
        if entity_id:
            return entity_id
        return ChaosSpaceMarinesDetachmentManager._unit_root_key(root)

    def _iter_unique_roots(self, units: Iterable) -> list:
        roots = []
        seen: set[str] = set()
        for unit in list(units or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            key = self._unit_root_key(root)
            if key in seen:
                continue
            seen.add(key)
            roots.append(root)
        return roots

    @staticmethod
    def _clear_unit_ability_cache(unit) -> None:
        if unit is None:
            return
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            maybe_root = get_root()
            if maybe_root is not None:
                root = maybe_root
        invalidate = getattr(root, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()
            return
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.clear()

    def _unit_in_army(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None or self.army is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _model_in_army(self, model) -> bool:
        if model is None:
            return False
        return self._unit_in_army(getattr(model, "parent_unit", None))

    def _unit_is_heretic_astartes(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return self._unit_has_keyword(root, "HERETIC ASTARTES")

    def _unit_is_damned(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return self._unit_has_keyword(root, "DAMNED")

    def _unit_is_daemon_vehicle(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return bool(self._unit_has_keyword(root, "DAEMON") and self._unit_has_keyword(root, "VEHICLE"))

    def _unit_is_battle_shocked(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        is_battle_shocked = getattr(root, "is_battle_shocked", None)
        if callable(is_battle_shocked):
            return bool(is_battle_shocked())
        return False

    def _unit_has_dark_pacts(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False

        has_dark_pacts = getattr(root, "has_dark_pacts", None)
        if callable(has_dark_pacts) and bool(has_dark_pacts()):
            return True

        for container_name in ("possible_abilities", "abilities"):
            for ability in list(getattr(root, container_name, []) or []):
                if isinstance(ability, str):
                    name = ability
                else:
                    name = getattr(ability, "name", "")
                if "dark pact" in str(name or "").strip().lower():
                    return True
        return False

    def _unit_arrived_from_reserves_this_turn(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return bool(getattr(root, "arrived_from_reserves_this_turn", False))

    def _unit_on_battlefield(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        in_reserves = getattr(root, "is_in_reserves", None)
        if callable(in_reserves) and bool(in_reserves()):
            return False
        return True

    def _unit_is_embarked(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None

    def _unit_matches_split_origin(self, unit, original_unit_id: str) -> bool:
        root = self._unit_root(unit)
        target_id = str(original_unit_id or "").strip()
        if root is None or not target_id:
            return False
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            return False
        for key, value in special_rules.items():
            if not str(key or "").endswith("_split_origin_unit_id"):
                continue
            if str(value or "").strip() == target_id:
                return True
        return False

    def _model_is_heretic_astartes(self, model) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any) and bool(has_any("HERETIC ASTARTES")):
            return True
        has_keyword = getattr(model, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword("HERETIC ASTARTES")):
            return True
        return self._unit_is_heretic_astartes(getattr(model, "parent_unit", None))

    def _uses_csm_terror_forced_battleshock_clause(self) -> bool:
        return bool(self.is_dread_talons() or self.is_nightmare_hunt())

    def csm_terror_forced_battleshock_source(self) -> str:
        if self.is_nightmare_hunt():
            return "Terror Made Manifest"
        return "Terror Descends"

    def terror_descends_source_units(self) -> list:
        if not self._uses_csm_terror_forced_battleshock_clause() or self.army is None:
            return []
        sources = []
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_heretic_astartes(root):
                continue
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive) and not bool(is_alive()):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            reserve_status = str(getattr(root, "reserve_status", "deployed") or "deployed").strip().lower()
            if reserve_status != "deployed":
                continue
            in_reserves = getattr(root, "is_in_reserves", None)
            if callable(in_reserves) and bool(in_reserves()):
                continue
            if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
                continue
            sources.append(root)
        sources.sort(key=lambda unit: str(get_entity_id(unit) or self._unit_root_key(unit)))
        return sources

    def terror_descends_target_in_range(self, target_unit) -> bool:
        if not self._uses_csm_terror_forced_battleshock_clause():
            return False
        root = self._unit_root(target_unit)
        if root is None:
            return False
        from ..utility.aura_utils import unit_within_range_of_unit

        for source in list(self.terror_descends_source_units() or []):
            if unit_within_range_of_unit(source, root, 12.0, use_attached_aggregate=True):
                return True
        return False

    def terror_descends_apply_test_suppression(
        self,
        target_unit,
        *,
        phase_name: str = "COMMAND_PHASE",
        allow_current_test: bool = False,
    ) -> None:
        root = self._unit_root(target_unit)
        if root is None:
            return
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        updated = dict(special_rules)
        updated["battle_shock_suppress_other_tests_phase"] = str(phase_name or "COMMAND_PHASE").strip().upper()
        updated["battle_shock_suppress_other_tests_source"] = self.csm_terror_forced_battleshock_source()
        if bool(allow_current_test):
            updated["battle_shock_allow_suppressed_test"] = True
        else:
            updated.pop("battle_shock_allow_suppressed_test", None)
        root.special_rules = updated

    def csm_terror_forced_battleshock_test_modifier(self, target_unit) -> tuple[int, str]:
        if not self.is_nightmare_hunt():
            return 0, ""
        root = self._unit_root(target_unit)
        if root is None:
            return 0, ""
        if not self.terror_descends_target_in_range(root):
            return 0, ""
        return -1, "Terror Made Manifest"

    def iron_fortitude_defensive_wound_mod_entry(self, target_unit) -> Optional[dict]:
        if not self.is_fellhammer_siege_host():
            return None
        root = self._unit_root(target_unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self._unit_is_heretic_astartes(root):
            return None
        if self._unit_is_damned(root):
            return None
        return {
            "value": 1,
            "attack_type": "ranged",
            "source": "Iron Fortitude",
            "requires_strength_gt_toughness": True,
            "tag": "detachment:iron_fortitude",
        }

    def fellhammer_ironbound_enmity_wound_bonus(self, attacker_model, target_unit, *, game=None) -> tuple[int, str]:
        if not self.is_fellhammer_siege_host():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        if not self._model_in_army(attacker_model):
            return 0, ""
        if not self._model_is_heretic_astartes(attacker_model):
            return 0, ""
        attacker_unit = self._unit_root(getattr(attacker_model, "parent_unit", None))
        if attacker_unit is None:
            return 0, ""
        _source_member, source_sr, bearer = self._fellhammer_siege_host_enhancement_source_member(
            attacker_unit,
            flag_key="enhancement_ironbound_enmity",
            require_bearer_alive=True,
            require_bearer_on_battlefield=False,
        )
        if source_sr is None or bearer is None:
            return 0, ""
        if not self._model_matches_bearer(attacker_model, bearer):
            return 0, ""
        if bool(source_sr.get("enhancement_ironbound_enmity_requires_within_objective_range", True)):
            resolved_game = self._resolve_game(game=game)
            game_map = getattr(resolved_game, "map", None) if resolved_game is not None else None
            within_any = getattr(attacker_unit, "is_within_any_objective_range", None)
            if not callable(within_any):
                return 0, ""
            if not bool(within_any(game_map)):
                return 0, ""
        try:
            bonus = int(source_sr.get("enhancement_ironbound_enmity_wound_roll_bonus", 1) or 1)
        except (TypeError, ValueError):
            bonus = 1
        if bonus <= 0:
            return 0, ""
        source = str(source_sr.get("enhancement_ironbound_enmity_source", "") or "Ironbound Enmity").strip()
        return bonus, (source or "Ironbound Enmity")

    def terror_made_manifest_hit_bonus(self, attacker_model, target_unit) -> tuple[int, str]:
        if not self.is_nightmare_hunt():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        if not self._model_in_army(attacker_model):
            return 0, ""
        if not self._model_is_heretic_astartes(attacker_model):
            return 0, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return 0, ""
        is_below_half_strength = getattr(target_root, "is_below_half_strength", None)
        if not callable(is_below_half_strength) or not bool(is_below_half_strength()):
            return 0, ""
        return 1, "Terror Made Manifest"

    def terror_made_manifest_attacker_battle_shocked_hit_penalty(self, attacker_model, target_unit) -> tuple[int, str]:
        if not self.is_nightmare_hunt():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return 0, ""
        if not self._unit_in_army(target_root):
            return 0, ""
        if not self._unit_is_heretic_astartes(target_root):
            return 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._unit_root(unit)
        if attacker_root is None:
            return 0, ""
        is_battle_shocked = getattr(attacker_root, "is_battle_shocked", None)
        if not callable(is_battle_shocked) or not bool(is_battle_shocked()):
            return 0, ""
        return 1, "Terror Made Manifest"

    def terror_made_manifest_wound_bonus(self, attacker_model, target_unit) -> tuple[int, str]:
        if not self.is_nightmare_hunt():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        if not self._model_in_army(attacker_model):
            return 0, ""
        if not self._model_is_heretic_astartes(attacker_model):
            return 0, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return 0, ""
        is_battle_shocked = getattr(target_root, "is_battle_shocked", None)
        if not callable(is_battle_shocked) or not bool(is_battle_shocked()):
            return 0, ""
        return 1, "Terror Made Manifest"

    def nightmare_hunt_greyveil_hex_ranged_targeting_cap(self, target_unit, *, game=None) -> tuple[float, str]:
        if not self.is_nightmare_hunt():
            return 0.0, ""
        root = self._unit_root(target_unit)
        if root is None or not self._unit_in_army(root):
            return 0.0, ""
        _source_member, source_sr, bearer = self._nightmare_hunt_enhancement_source_member(
            root,
            flag_key="enhancement_greyveil_hex",
            require_bearer_alive=False,
            require_bearer_on_battlefield=False,
        )
        if source_sr is None or bearer is None:
            return 0.0, ""
        if bool(source_sr.get("enhancement_greyveil_hex_requires_bearer_alive", True)):
            if not self._model_alive(bearer):
                return 0.0, ""
        if bool(source_sr.get("enhancement_greyveil_hex_requires_within_controlled_objective_range", True)):
            resolved_game = self._resolve_game(game=game)
            game_map = getattr(resolved_game, "map", None) if resolved_game is not None else None
            within_controlled = getattr(root, "_within_controlled_objective_range", None)
            if not callable(within_controlled):
                return 0.0, ""
            if not bool(within_controlled(game_map)):
                return 0.0, ""
        try:
            cap = float(source_sr.get("enhancement_greyveil_hex_ranged_targeting_max_distance", 18.0) or 18.0)
        except (TypeError, ValueError):
            cap = 18.0
        source = str(source_sr.get("enhancement_greyveil_hex_source", "") or "Greyveil Hex").strip() or "Greyveil Hex"
        return max(0.0, cap), source

    @classmethod
    def _tyrannical_motivation_choice_label(cls, choice_key: str) -> str:
        key = str(choice_key or "").strip().upper()
        if key == cls._TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE:
            return "Huron's Elite"
        if key == cls._TYRANNICAL_MOTIVATION_CHOICE_MOBILE_MARAUDERS:
            return "Mobile Marauders"
        return key

    @classmethod
    def _hardened_killers_choice_label(cls, choice_key: str) -> str:
        key = str(choice_key or "").strip().upper()
        if key == cls._HARDENED_KILLERS_CHOICE_BALLISTIC_SKILL:
            return "Ballistic Skill"
        if key == cls._HARDENED_KILLERS_CHOICE_RAPID_FIRE:
            return "Rapid Fire"
        if key == cls._HARDENED_KILLERS_CHOICE_SAVE:
            return "Save"
        return key

    @classmethod
    def _is_huron_blackheart_unit(cls, unit) -> bool:
        return cls._normalize_name(str(getattr(unit, "name", "") or "")) == "huron blackheart"

    def _unit_is_heretic_astartes_infantry(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_has_keyword(root, "HERETIC ASTARTES"):
            return False
        if not self._unit_has_keyword(root, "INFANTRY"):
            return False
        return True

    def _tyrannical_motivation_unit_id(self, unit) -> str:
        root = self._unit_root(unit)
        if root is None:
            return ""
        return str(get_entity_id(root) or self._unit_root_key(root))

    def _clear_tyrannical_motivation_phase_snapshot(self) -> None:
        self._tyrannical_motivation_phase_signature = None
        self._tyrannical_motivation_phase_hit_bonus_unit_ids = set()
        self._tyrannical_motivation_phase_mobile_unit_ids = set()

    def clear_tyrannical_motivation_choice(self) -> None:
        self.tyrannical_motivation_choice_key = ""
        self._clear_tyrannical_motivation_phase_snapshot()

    def can_select_tyrannical_motivation_choice(self, *, game=None, player=None) -> bool:
        if not self.is_hurons_marauders() or self.army is None:
            return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        army_player = getattr(self.army, "player", None)
        if army_player is not None:
            if str(getattr(army_player, "id", "") or "") != str(getattr(owner, "id", "") or ""):
                return False
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return False
        phase_name = self._current_phase_name(game=resolved_game)
        if phase_name and phase_name != "COMMAND_PHASE":
            return False
        current_owner = str(self._current_turn_owner_id(game=resolved_game, player=owner) or "")
        if current_owner and current_owner != str(getattr(owner, "id", "") or ""):
            return False
        return True

    def _pending_tyrannical_motivation_choice_request(self, game, *, army_id: str, battle_round: int) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != self._TYRANNICAL_MOTIVATION_ABILITY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            ctx_round = int(ctx.get("battle_round", battle_round) or battle_round)
            if int(ctx_round) == int(battle_round):
                return True
        return False

    def queue_tyrannical_motivation_choice_request(self, *, game=None, player=None) -> None:
        if not self.is_hurons_marauders() or self.army is None:
            return
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None or not bool(getattr(resolved_game, "is_authoritative", True)):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        if not self.can_select_tyrannical_motivation_choice(game=resolved_game, player=owner):
            return
        self.clear_tyrannical_motivation_choice()

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        army_id = str(get_entity_id(self.army) or "")
        battle_round = int(self._current_turn(game=resolved_game) or 0)
        if self._pending_tyrannical_motivation_choice_request(
            resolved_game,
            army_id=army_id,
            battle_round=battle_round,
        ):
            return

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Tyrannical Motivation: select Huron's Elite or Mobile Marauders.",
            player_id=getattr(owner, "id", None),
            options=[
                DecisionOption.create(
                    "Huron's Elite",
                    payload={
                        "choice_key": self._TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE,
                        "summary": "HERETIC ASTARTES INFANTRY units gain +1 to hit until your next Command phase.",
                        "army_id": army_id,
                    },
                ),
                DecisionOption.create(
                    "Mobile Marauders",
                    payload={
                        "choice_key": self._TYRANNICAL_MOTIVATION_CHOICE_MOBILE_MARAUDERS,
                        "summary": "HERETIC ASTARTES INFANTRY units can shoot and charge after Falling Back until your next Command phase.",
                        "army_id": army_id,
                    },
                ),
            ],
            context={
                "ability": self._TYRANNICAL_MOTIVATION_ABILITY,
                "ability_name": self._TYRANNICAL_MOTIVATION_SOURCE,
                "phase": "Command phase",
                "army_id": army_id,
                "battle_round": int(battle_round),
                "allowed_choice_keys": [
                    self._TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE,
                    self._TYRANNICAL_MOTIVATION_CHOICE_MOBILE_MARAUDERS,
                ],
            },
        )
        if hasattr(resolved_game, "request_decision"):
            resolved_game.request_decision(request)

    def select_tyrannical_motivation_choice(self, choice_key: str, *, game=None, player=None) -> dict:
        if not self.can_select_tyrannical_motivation_choice(game=game, player=player):
            return {"ok": False, "reason": "Tyrannical Motivation cannot be selected right now."}
        choice = str(choice_key or "").strip().upper()
        allowed = {
            self._TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE,
            self._TYRANNICAL_MOTIVATION_CHOICE_MOBILE_MARAUDERS,
        }
        if choice not in allowed:
            return {"ok": False, "reason": "Tyrannical Motivation choice is invalid."}
        self.tyrannical_motivation_choice_key = choice
        self._clear_tyrannical_motivation_phase_snapshot()
        self.refresh_tyrannical_motivation_phase_state(game=game, force=True)
        return {
            "ok": True,
            "choice_key": choice,
            "label": self._tyrannical_motivation_choice_label(choice),
            "source": self._TYRANNICAL_MOTIVATION_SOURCE,
        }

    def _iter_huron_blackheart_source_units(self) -> list:
        if self.army is None:
            return []
        sources = []
        seen: set[str] = set()
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            members_fn = getattr(root, "get_attached_unit_members", None)
            members = list(members_fn() or []) if callable(members_fn) else [root]
            if not members:
                members = [root]
            for member in members:
                if member is None:
                    continue
                if not self._is_huron_blackheart_unit(member):
                    continue
                if not self._unit_on_battlefield(member):
                    continue
                is_alive = getattr(member, "is_alive", None)
                if callable(is_alive) and not bool(is_alive()):
                    continue
                key = str(get_entity_id(member) or self._unit_root_key(member))
                if key in seen:
                    continue
                seen.add(key)
                sources.append(member)
        sources.sort(key=lambda unit: str(get_entity_id(unit) or self._unit_root_key(unit)))
        return sources

    def _unit_visible_to_friendly_huron(self, unit, *, game=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_on_battlefield(root):
            return False
        sources = list(self._iter_huron_blackheart_source_units() or [])
        if not sources:
            return False
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return False
        resolved_map = getattr(resolved_game, "map", None)
        can_see_unit_fn = getattr(resolved_game, "_model_can_see_unit", None)
        can_see_model_fn = getattr(resolved_map, "can_model_see_model", None) if resolved_map is not None else None
        if not callable(can_see_unit_fn) and not callable(can_see_model_fn):
            return False

        target_models_fn = getattr(root, "get_attached_unit_models", None)
        target_models = list(target_models_fn() or []) if callable(target_models_fn) else list(getattr(root, "models", []) or [])
        for source in sources:
            source_root = self._unit_root(source)
            if source_root is root:
                return True
            source_models_fn = getattr(source, "get_attached_unit_models", None)
            source_models = list(source_models_fn() or []) if callable(source_models_fn) else list(getattr(source, "models", []) or [])
            for sm in source_models:
                if sm is None:
                    continue
                try:
                    if not getattr(sm, "is_alive", True):
                        continue
                except Exception:
                    continue
                if callable(can_see_unit_fn):
                    try:
                        if bool(can_see_unit_fn(sm, root, game_map=resolved_map)):
                            return True
                    except Exception:
                        pass
                if callable(can_see_unit_fn):
                    continue
                if callable(can_see_model_fn):
                    for tm in target_models:
                        if tm is None:
                            continue
                        try:
                            if not getattr(tm, "is_alive", True):
                                continue
                        except Exception:
                            continue
                        try:
                            if bool(can_see_model_fn(sm, tm)):
                                return True
                        except Exception:
                            continue
        return False

    def refresh_tyrannical_motivation_phase_state(self, *, game=None, force: bool = False) -> None:
        if not self.is_hurons_marauders() or self.army is None:
            self._clear_tyrannical_motivation_phase_snapshot()
            return
        resolved_game = self._resolve_game(game=game)
        phase_signature = (
            str(self._current_phase_name(game=resolved_game) or ""),
            int(self._current_turn(game=resolved_game) or 0),
            str(self._current_turn_owner_id(game=resolved_game) or ""),
        )
        if (not force) and phase_signature == self._tyrannical_motivation_phase_signature:
            return
        self._tyrannical_motivation_phase_signature = phase_signature
        self._tyrannical_motivation_phase_hit_bonus_unit_ids = set()
        self._tyrannical_motivation_phase_mobile_unit_ids = set()

        choice_key = str(self.tyrannical_motivation_choice_key or "").strip().upper()
        if choice_key not in {
            self._TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE,
            self._TYRANNICAL_MOTIVATION_CHOICE_MOBILE_MARAUDERS,
        }:
            return

        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_heretic_astartes_infantry(root):
                continue
            unit_id = self._tyrannical_motivation_unit_id(root)
            if not unit_id:
                continue
            if not self._unit_visible_to_friendly_huron(root, game=resolved_game):
                continue
            if choice_key == self._TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE:
                self._tyrannical_motivation_phase_mobile_unit_ids.add(unit_id)
            else:
                self._tyrannical_motivation_phase_hit_bonus_unit_ids.add(unit_id)

    def _tyrannical_motivation_effects_for_unit(self, unit, *, game=None) -> tuple[bool, bool]:
        if not self.is_hurons_marauders():
            return False, False
        root = self._unit_root(unit)
        if root is None:
            return False, False
        if not self._unit_in_army(root):
            return False, False
        if not self._unit_is_heretic_astartes_infantry(root):
            return False, False

        _voice_root, _voice_member, voice_sr, _voice_bearer = self._hurons_marauders_enhancement_source_member(
            root,
            flag_key="enhancement_voice_of_the_tyrant",
            require_bearer_alive=True,
            require_bearer_on_battlefield=False,
        )
        voice_grants_hurons_elite = bool(
            isinstance(voice_sr, dict) and bool(voice_sr.get("enhancement_voice_of_the_tyrant_grant_hurons_elite", True))
        )
        voice_grants_mobile_marauders = bool(
            isinstance(voice_sr, dict)
            and bool(voice_sr.get("enhancement_voice_of_the_tyrant_grant_mobile_marauders", True))
        )

        choice_key = str(self.tyrannical_motivation_choice_key or "").strip().upper()
        if choice_key not in {
            self._TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE,
            self._TYRANNICAL_MOTIVATION_CHOICE_MOBILE_MARAUDERS,
        }:
            return voice_grants_hurons_elite, voice_grants_mobile_marauders

        self.refresh_tyrannical_motivation_phase_state(game=game)
        unit_id = self._tyrannical_motivation_unit_id(root)
        if not unit_id:
            return voice_grants_hurons_elite, voice_grants_mobile_marauders
        has_hit_bonus = bool(choice_key == self._TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE)
        has_mobile_marauders = bool(choice_key == self._TYRANNICAL_MOTIVATION_CHOICE_MOBILE_MARAUDERS)
        if voice_grants_hurons_elite:
            has_hit_bonus = True
        if voice_grants_mobile_marauders:
            has_mobile_marauders = True
        if unit_id in self._tyrannical_motivation_phase_hit_bonus_unit_ids:
            has_hit_bonus = True
        if unit_id in self._tyrannical_motivation_phase_mobile_unit_ids:
            has_mobile_marauders = True
        return has_hit_bonus, has_mobile_marauders

    def tyrannical_motivation_hit_bonus(self, attacker_model, *, game=None) -> tuple[int, str]:
        unit = getattr(attacker_model, "parent_unit", None) if attacker_model is not None else None
        has_hit_bonus, _has_mobile = self._tyrannical_motivation_effects_for_unit(unit, game=game)
        if not has_hit_bonus:
            return 0, ""
        return 1, f"{self._TYRANNICAL_MOTIVATION_SOURCE} (Huron's Elite)"

    def tyrannical_motivation_can_shoot_after_fall_back(self, unit, profile=None, *, game=None) -> bool:
        _has_hit_bonus, has_mobile = self._tyrannical_motivation_effects_for_unit(unit, game=game)
        if not has_mobile:
            return False
        parent = getattr(profile, "parent_wargear", None) if profile is not None else None
        is_ranged = getattr(parent, "is_ranged", None) if parent is not None else None
        if callable(is_ranged):
            return bool(is_ranged())
        return True

    def tyrannical_motivation_can_charge_after_fall_back(self, unit, *, game=None) -> bool:
        _has_hit_bonus, has_mobile = self._tyrannical_motivation_effects_for_unit(unit, game=game)
        return bool(has_mobile)

    def hurons_marauders_raid_leader_allows_charge_after_normal_move_disembark(
        self,
        unit,
        *,
        transport_unit=None,
        game=None,
    ) -> bool:
        _ = game
        if not self.is_hurons_marauders():
            return False
        root, _source_member, source_sr, _bearer = self._hurons_marauders_enhancement_source_member(
            unit,
            flag_key="enhancement_raid_leader",
            require_bearer_alive=True,
            require_bearer_on_battlefield=False,
        )
        if source_sr is None:
            return False
        if not bool(source_sr.get("enhancement_raid_leader_allow_charge_after_normal_move", True)):
            return False
        if not bool(source_sr.get("enhancement_raid_leader_requires_disembarked_from_moved_transport", True)):
            return True

        if transport_unit is not None:
            moved_this_round = bool(getattr(getattr(transport_unit, "round_state", None), "moved_this_round", False))
            remained_stationary = bool(
                getattr(getattr(transport_unit, "round_state", None), "remained_stationary_this_round", False)
            )
            advanced = bool(getattr(getattr(transport_unit, "round_state", None), "advanced_this_round", False))
            fell_back = bool(getattr(getattr(transport_unit, "round_state", None), "fell_back_this_round", False))
            return bool(moved_this_round and not remained_stationary and not advanced and not fell_back)

        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "disembarked_from_destroyed_transport", False)):
            return False
        return bool(getattr(round_state, "disembarked_from_moved_transport", False))

    def _dread_reputation_enemy_units_in_range(
        self,
        *,
        source_unit,
        game,
        range_in: float,
    ) -> list:
        if source_unit is None or game is None:
            return []
        owner = getattr(self.army, "player", None) if self.army is not None else None
        if owner is None:
            return []
        get_enemy_units = getattr(game, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        from ..utility.aura_utils import min_distance_between_units_3d, unit_within_range_of_unit

        out: list[tuple[float, str, object]] = []
        seen: set[str] = set()
        for enemy in list(get_enemy_units(owner) or []):
            enemy_root = self._unit_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = str(get_entity_id(enemy_root) or self._unit_root_key(enemy_root))
            if not enemy_id or enemy_id in seen:
                continue
            if not self._unit_on_battlefield(enemy_root):
                continue
            if not bool(unit_within_range_of_unit(source_unit, enemy_root, float(range_in), use_attached_aggregate=True)):
                continue
            distance = float(min_distance_between_units_3d(source_unit, enemy_root, use_attached_aggregate=True))
            out.append((distance, enemy_id, enemy_root))
            seen.add(enemy_id)
        out.sort(key=lambda entry: (entry[0], entry[1]))
        return [entry[2] for entry in out]

    def on_unit_set_up(
        self,
        *,
        unit=None,
        game=None,
        set_up_as_reinforcements: bool = False,
        used_deep_strike: bool = False,
        set_up_from_disembark: bool = False,
    ) -> None:
        _ = set_up_from_disembark
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        root = self._unit_root(unit)
        if root is None:
            return

        if self.is_hurons_marauders():
            root, _source_member, source_sr, _bearer = self._hurons_marauders_enhancement_source_member(
                unit,
                flag_key="enhancement_dread_reputation",
                require_bearer_alive=True,
                require_bearer_on_battlefield=False,
            )
            if source_sr is not None and root is not None and self._unit_in_army(root) and self._unit_on_battlefield(root):
                try:
                    base_range = float(source_sr.get("enhancement_dread_reputation_range_in", 6.0) or 6.0)
                except (TypeError, ValueError):
                    base_range = 6.0
                try:
                    deep_strike_range = float(
                        source_sr.get("enhancement_dread_reputation_deep_strike_range_in", 12.0) or 12.0
                    )
                except (TypeError, ValueError):
                    deep_strike_range = 12.0
                if base_range < 0.0:
                    base_range = 0.0
                if deep_strike_range < 0.0:
                    deep_strike_range = 0.0
                used_deep_strike_setup = bool(used_deep_strike)
                if not used_deep_strike_setup and bool(set_up_as_reinforcements):
                    has_deep_strike = getattr(root, "has_deep_strike", None)
                    if callable(has_deep_strike):
                        used_deep_strike_setup = bool(has_deep_strike())
                effective_range = float(deep_strike_range if used_deep_strike_setup else base_range)
                if effective_range > 0.0:
                    current_turn = int(self._current_turn(game=game) or 1)
                    for enemy in self._dread_reputation_enemy_units_in_range(
                        source_unit=root,
                        game=game,
                        range_in=effective_range,
                    ):
                        take_test = getattr(enemy, "take_battle_shock_test", None)
                        if callable(take_test):
                            take_test(current_turn)

        if not self.is_dread_talons():
            return
        if not bool(set_up_as_reinforcements):
            return
        if not self._unit_in_army(root) or not self._unit_on_battlefield(root):
            return

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        pending_key = f"{self._DREAD_TALONS_SCREAMING_DESCENT_PREFIX}_post_setup_battleshock_pending"
        if not bool(sr.get(pending_key, False)):
            return
        sr.pop(pending_key, None)
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

        owner = getattr(self.army, "player", None) if self.army is not None else None
        get_enemy_units = getattr(game, "get_enemy_units", None)
        if owner is None or not callable(get_enemy_units):
            return

        from ..utility.aura_utils import unit_within_range_of_unit

        los_checker = getattr(root, "_attacking_unit_has_any_los_to_target_unit", None)
        current_turn = int(self._current_turn(game=game) or 1)
        ability_name = (
            str(sr.get(f"{self._DREAD_TALONS_SCREAMING_DESCENT_PREFIX}_source", "") or self._DREAD_TALONS_SCREAMING_DESCENT_SOURCE).strip()
            or self._DREAD_TALONS_SCREAMING_DESCENT_SOURCE
        )

        candidates: list[object] = []
        seen: set[str] = set()
        for enemy in list(get_enemy_units(owner) or []):
            enemy_root = self._unit_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = str(get_entity_id(enemy_root) or self._unit_root_key(enemy_root))
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if not self._unit_on_battlefield(enemy_root):
                continue
            if not (self._unit_has_keyword(enemy_root, "INFANTRY") or self._unit_has_keyword(enemy_root, "MOUNTED")):
                continue
            if not bool(unit_within_range_of_unit(root, enemy_root, 9.0, use_attached_aggregate=True)):
                continue
            if not callable(los_checker) or not bool(los_checker(enemy_root, getattr(game, "map", None))):
                continue
            candidates.append(enemy_root)
        candidates.sort(key=lambda unit_obj: str(get_entity_id(unit_obj) or self._unit_root_key(unit_obj)))
        if not candidates:
            return
        if len(candidates) == 1:
            take_test = getattr(candidates[0], "take_battle_shock_test", None)
            if callable(take_test):
                take_test(current_turn)
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        root_id = str(get_entity_id(root) or "")
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("attacker_unit_id", "") or "") != root_id:
                    continue
                if str(ctx.get("ability_name", "") or "").strip() != ability_name:
                    continue
                return

        request = DecisionRequest.create(
            DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
            f"{ability_name}: select an enemy unit to take a Battle-shock test.",
            player_id=getattr(owner, "id", None),
            options=[
                DecisionOption.create(
                    str(getattr(target_root, "name", "Unit") or "Unit"),
                    payload={"unit_id": get_entity_id(target_root)},
                )
                for target_root in list(candidates)
            ],
            context={
                "attacker_unit_id": root_id,
                "ability_name": ability_name,
            },
        )
        request_decision = getattr(game, "request_decision", None)
        if callable(request_decision):
            request_decision(request)
            return

        take_test = getattr(candidates[0], "take_battle_shock_test", None)
        if callable(take_test):
            take_test(current_turn)

    def clear_renegade_warband_vendetta_target(self) -> None:
        self.renegade_warband_vendetta_target_unit_id = ""
        self.clear_renegade_warband_weaponised_hatred_target()

    def clear_renegade_warband_weaponised_hatred_target(self) -> None:
        self.renegade_warband_weaponised_hatred_target_unit_id = ""
        self._renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id = ""

    def _weaponised_hatred_source_entry(self):
        if not self.is_renegade_warband() or self.army is None:
            return None
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            source_root, source_member, source_sr, source_bearer = self._renegade_warband_enhancement_source_member(
                root,
                flag_key="enhancement_weaponised_hatred",
                require_bearer_alive=True,
                require_bearer_on_battlefield=True,
            )
            if source_root is None or source_member is None or source_sr is None or source_bearer is None:
                continue
            if not self._unit_on_battlefield(source_root):
                continue
            return source_root, source_member, source_sr, source_bearer
        return None

    def _weaponised_hatred_target_visible_to_bearer(self, target_unit, *, source_bearer, game=None) -> bool:
        if target_unit is None or source_bearer is None:
            return False
        target_root = self._unit_root(target_unit)
        if target_root is None or not self._unit_on_battlefield(target_root):
            return False
        source_unit = self._unit_root(getattr(source_bearer, "parent_unit", None))
        if source_unit is target_root:
            return True
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return False
        resolved_map = getattr(resolved_game, "map", None)
        can_see_unit_fn = getattr(resolved_game, "_model_can_see_unit", None)
        if callable(can_see_unit_fn):
            try:
                return bool(can_see_unit_fn(source_bearer, target_root, game_map=resolved_map))
            except TypeError:
                return bool(can_see_unit_fn(source_bearer, target_root))
        can_see_model_fn = getattr(resolved_map, "can_model_see_model", None) if resolved_map is not None else None
        if not callable(can_see_model_fn):
            return True
        target_models_fn = getattr(target_root, "get_attached_unit_models", None)
        target_models = (
            list(target_models_fn() or [])
            if callable(target_models_fn)
            else list(getattr(target_root, "models", []) or [])
        )
        for tm in target_models:
            if tm is None or not bool(getattr(tm, "is_alive", True)):
                continue
            if bool(can_see_model_fn(source_bearer, tm)):
                return True
        return False

    def _iter_enemy_units_for_player(self, *, game=None, player=None) -> list:
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return []
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return []
        get_enemy_units = getattr(resolved_game, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        enemies = list(get_enemy_units(owner) or [])
        out: list = []
        seen: set[str] = set()
        for unit in enemies:
            root = self._unit_root(unit)
            if root is None:
                continue
            unit_id = str(get_entity_id(root) or self._unit_root_key(root))
            if not unit_id or unit_id in seen:
                continue
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive) and not bool(is_alive()):
                continue
            out.append(root)
            seen.add(unit_id)
        out.sort(key=lambda unit: str(get_entity_id(unit) or self._unit_root_key(unit)))
        return out

    def vendetta_candidate_enemy_units(self, *, game=None, player=None) -> list:
        if not self.is_renegade_warband() or self.army is None:
            return []
        return self._iter_enemy_units_for_player(game=game, player=player)

    def weaponised_hatred_candidate_enemy_units(self, *, game=None, player=None) -> list:
        if not self.is_renegade_warband() or self.army is None:
            return []
        source_entry = self._weaponised_hatred_source_entry()
        if source_entry is None:
            return []
        _source_root, _source_member, _source_sr, source_bearer = source_entry
        vendetta_target_id = str(self.renegade_warband_vendetta_target_unit_id or "").strip()
        pending_destroyed_target_id = str(
            self._renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id or ""
        ).strip()
        resolved_game = self._resolve_game(game=game)
        out = []
        for unit in list(self.vendetta_candidate_enemy_units(game=game, player=player) or []):
            unit_id = str(get_entity_id(unit) or "").strip()
            if not unit_id:
                continue
            if vendetta_target_id and unit_id == vendetta_target_id:
                continue
            if pending_destroyed_target_id and unit_id == pending_destroyed_target_id:
                continue
            if not self._weaponised_hatred_target_visible_to_bearer(
                unit,
                source_bearer=source_bearer,
                game=resolved_game,
            ):
                continue
            out.append(unit)
        out.sort(key=lambda unit: str(get_entity_id(unit) or self._unit_root_key(unit)))
        return out

    def _pending_vendetta_choice_request(self, game, *, army_id: str, battle_round: int) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != self._RENEGADE_WARBAND_VENDETTA_ABILITY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            try:
                ctx_round = int(ctx.get("battle_round", battle_round) or battle_round)
            except (TypeError, ValueError):
                ctx_round = int(battle_round or 0)
            if int(ctx_round) == int(battle_round):
                return True
        return False

    def _pending_weaponised_hatred_choice_request(self, game, *, army_id: str, battle_round: int) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != self._RENEGADE_WARBAND_WEAPONISED_HATRED_ABILITY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            try:
                ctx_round = int(ctx.get("battle_round", battle_round) or battle_round)
            except (TypeError, ValueError):
                ctx_round = int(battle_round or 0)
            if int(ctx_round) == int(battle_round):
                return True
        return False

    def can_select_vendetta_target(self, *, game=None, player=None) -> bool:
        if not self.is_renegade_warband() or self.army is None:
            return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        army_player = getattr(self.army, "player", None)
        if army_player is not None:
            if str(getattr(army_player, "id", "") or "") != str(getattr(owner, "id", "") or ""):
                return False
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return False
        phase_name = self._current_phase_name(game=resolved_game)
        if phase_name and phase_name != "COMMAND_PHASE":
            return False
        current_owner = str(self._current_turn_owner_id(game=resolved_game, player=owner) or "")
        if current_owner and current_owner != str(getattr(owner, "id", "") or ""):
            return False
        return True

    def can_select_weaponised_hatred_target(self, *, game=None, player=None) -> bool:
        if not self.is_renegade_warband() or self.army is None:
            return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        army_player = getattr(self.army, "player", None)
        if army_player is not None:
            if str(getattr(army_player, "id", "") or "") != str(getattr(owner, "id", "") or ""):
                return False
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return False
        if not str(self._renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id or "").strip():
            return False
        battle_round = int(self._current_turn(game=resolved_game) or 0)
        if battle_round > 0 and int(self._renegade_warband_weaponised_hatred_last_used_battle_round or 0) == battle_round:
            return False
        if self._weaponised_hatred_source_entry() is None:
            return False
        return True

    def queue_renegade_warband_vendetta_choice_request(self, *, game=None, player=None) -> None:
        if not self.is_renegade_warband() or self.army is None:
            return
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None or not bool(getattr(resolved_game, "is_authoritative", True)):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        if not self.can_select_vendetta_target(game=resolved_game, player=owner):
            return

        self.clear_renegade_warband_vendetta_target()

        candidates = list(self.vendetta_candidate_enemy_units(game=resolved_game, player=owner) or [])
        if not candidates:
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        army_id = str(get_entity_id(self.army) or "")
        battle_round = int(self._current_turn(game=resolved_game) or 0)
        if self._pending_vendetta_choice_request(
            resolved_game,
            army_id=army_id,
            battle_round=battle_round,
        ):
            return

        options: list[DecisionOption] = []
        candidate_ids: list[str] = []
        for unit in candidates:
            unit_id = str(get_entity_id(unit) or "")
            if not unit_id:
                continue
            candidate_ids.append(unit_id)
            options.append(
                DecisionOption.create(
                    str(getattr(unit, "name", "Enemy Unit") or "Enemy Unit"),
                    payload={
                        "target_unit_id": unit_id,
                        "army_id": army_id,
                    },
                )
            )
        if not options:
            return

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Vendetta: select one enemy unit.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._RENEGADE_WARBAND_VENDETTA_ABILITY,
                "ability_name": self._RENEGADE_WARBAND_VENDETTA_SOURCE,
                "phase": "Command phase",
                "army_id": army_id,
                "battle_round": int(battle_round),
                "candidate_unit_ids": list(candidate_ids),
                "optional": False,
            },
        )
        if hasattr(resolved_game, "request_decision"):
            resolved_game.request_decision(request)

    def queue_renegade_warband_weaponised_hatred_choice_request(self, *, game=None, player=None) -> bool:
        if not self.is_renegade_warband() or self.army is None:
            return False
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None or not bool(getattr(resolved_game, "is_authoritative", True)):
            return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        if not self.can_select_weaponised_hatred_target(game=resolved_game, player=owner):
            return False

        candidates = list(self.weaponised_hatred_candidate_enemy_units(game=resolved_game, player=owner) or [])
        if not candidates:
            self._renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id = ""
            return False

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        army_id = str(get_entity_id(self.army) or "")
        battle_round = int(self._current_turn(game=resolved_game) or 0)
        if self._pending_weaponised_hatred_choice_request(
            resolved_game,
            army_id=army_id,
            battle_round=battle_round,
        ):
            return False

        options: list[DecisionOption] = [DecisionOption.create("None", payload={"action": "skip", "army_id": army_id})]
        candidate_ids: list[str] = []
        for unit in candidates:
            unit_id = str(get_entity_id(unit) or "").strip()
            if not unit_id:
                continue
            candidate_ids.append(unit_id)
            options.append(
                DecisionOption.create(
                    str(getattr(unit, "name", "Enemy Unit") or "Enemy Unit"),
                    payload={
                        "target_unit_id": unit_id,
                        "army_id": army_id,
                    },
                )
            )
        if not options:
            self._renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id = ""
            return False

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Weaponised Hatred: select one visible enemy unit to become your Vendetta target (or None).",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._RENEGADE_WARBAND_WEAPONISED_HATRED_ABILITY,
                "ability_name": self._RENEGADE_WARBAND_WEAPONISED_HATRED_SOURCE,
                "phase": "Reactive (after Vendetta target destroyed)",
                "army_id": army_id,
                "battle_round": int(battle_round),
                "destroyed_vendetta_target_unit_id": str(
                    self._renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id or ""
                ).strip(),
                "candidate_unit_ids": list(candidate_ids),
                "optional": True,
            },
        )
        if hasattr(resolved_game, "request_decision"):
            resolved_game.request_decision(request)
            return True
        return False

    def vendetta_target_is_valid(self, target_unit_id: str, *, game=None, player=None) -> bool:
        target_id = str(target_unit_id or "").strip()
        if not target_id:
            return False
        candidates = list(self.vendetta_candidate_enemy_units(game=game, player=player) or [])
        candidate_ids = {str(get_entity_id(unit) or "") for unit in candidates}
        return target_id in candidate_ids

    def weaponised_hatred_target_is_valid(self, target_unit_id: str, *, game=None, player=None) -> bool:
        target_id = str(target_unit_id or "").strip()
        if not target_id:
            return False
        vendetta_target_id = str(self.renegade_warband_vendetta_target_unit_id or "").strip()
        if vendetta_target_id and target_id == vendetta_target_id:
            return False
        candidates = list(self.weaponised_hatred_candidate_enemy_units(game=game, player=player) or [])
        candidate_ids = {str(get_entity_id(unit) or "").strip() for unit in candidates}
        return target_id in candidate_ids

    def select_vendetta_target(self, target_unit_id: str, *, game=None, player=None) -> dict:
        if not self.can_select_vendetta_target(game=game, player=player):
            return {"ok": False, "reason": "Vendetta target cannot be selected right now."}
        target_id = str(target_unit_id or "").strip()
        if not self.vendetta_target_is_valid(target_id, game=game, player=player):
            return {"ok": False, "reason": "Vendetta target is invalid."}
        self.renegade_warband_vendetta_target_unit_id = target_id
        self.clear_renegade_warband_weaponised_hatred_target()
        target_name = ""
        for unit in list(self.vendetta_candidate_enemy_units(game=game, player=player) or []):
            if str(get_entity_id(unit) or "") == target_id:
                target_name = str(getattr(unit, "name", "") or "").strip()
                break
        return {
            "ok": True,
            "target_unit_id": target_id,
            "target_name": target_name or "Enemy Unit",
            "source": self._RENEGADE_WARBAND_VENDETTA_SOURCE,
        }

    def select_weaponised_hatred_target(self, target_unit_id: str, *, game=None, player=None) -> dict:
        if not self.can_select_weaponised_hatred_target(game=game, player=player):
            return {"ok": False, "reason": "Weaponised Hatred target cannot be selected right now."}
        target_id = str(target_unit_id or "").strip()
        if not target_id:
            self.renegade_warband_weaponised_hatred_target_unit_id = ""
            self._renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id = ""
            current_round = int(self._current_turn(game=game) or 0)
            if current_round > 0:
                self._renegade_warband_weaponised_hatred_last_used_battle_round = current_round
            return {
                "ok": True,
                "skipped": True,
                "source": self._RENEGADE_WARBAND_WEAPONISED_HATRED_SOURCE,
            }
        if not self.weaponised_hatred_target_is_valid(target_id, game=game, player=player):
            return {"ok": False, "reason": "Weaponised Hatred target is invalid."}
        self.renegade_warband_vendetta_target_unit_id = target_id
        self.renegade_warband_weaponised_hatred_target_unit_id = target_id
        self._renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id = ""
        current_round = int(self._current_turn(game=game) or 0)
        if current_round > 0:
            self._renegade_warband_weaponised_hatred_last_used_battle_round = current_round
        target_name = ""
        for unit in list(self.weaponised_hatred_candidate_enemy_units(game=game, player=player) or []):
            if str(get_entity_id(unit) or "").strip() == target_id:
                target_name = str(getattr(unit, "name", "") or "").strip()
                break
        return {
            "ok": True,
            "target_unit_id": target_id,
            "target_name": target_name or "Enemy Unit",
            "source": self._RENEGADE_WARBAND_WEAPONISED_HATRED_SOURCE,
        }

    def _renegade_warband_enhancement_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_on_battlefield: bool = False,
    ):
        if not self.is_renegade_warband():
            return None, None, None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None, None, None
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
                continue
            bearer = self._find_enhancement_bearer_on_member(member, sr)
            if require_bearer_alive and not self._model_alive(bearer):
                continue
            if require_bearer_on_battlefield:
                bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None))
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue
            return root, member, sr, bearer
        return None, None, None, None

    def _renegade_warband_first_enhancement_source(
        self,
        *,
        flag_key: str,
        require_bearer_alive: bool,
        require_bearer_on_battlefield: bool,
    ) -> Unit | None:
        if self.army is None:
            return None
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            source_root, _member, _sr, _bearer = self._renegade_warband_enhancement_source_member(
                root,
                flag_key=flag_key,
                require_bearer_alive=require_bearer_alive,
                require_bearer_on_battlefield=require_bearer_on_battlefield,
            )
            if source_root is not None:
                return source_root
        return None

    def _promote_weaponised_hatred_target_if_needed(self, destroyed_unit_id: str) -> bool:
        primary_target = str(self.renegade_warband_vendetta_target_unit_id or "").strip()
        if not primary_target or primary_target != str(destroyed_unit_id or "").strip():
            return False
        resolved_game = self._resolve_game(game=None)
        owner = getattr(self.army, "player", None) if self.army is not None else None
        battle_round = int(self._current_turn(game=resolved_game) or 0)

        self.renegade_warband_vendetta_target_unit_id = ""
        self.renegade_warband_weaponised_hatred_target_unit_id = ""

        if battle_round > 0 and int(self._renegade_warband_weaponised_hatred_last_used_battle_round or 0) == battle_round:
            self._renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id = ""
            return False
        if self._weaponised_hatred_source_entry() is None:
            self._renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id = ""
            return False

        self._renegade_warband_weaponised_hatred_pending_destroyed_vendetta_unit_id = primary_target
        return bool(self.queue_renegade_warband_weaponised_hatred_choice_request(game=resolved_game, player=owner))

    def renegade_warband_ignores_cover_active(self, unit: Unit, *, attack_type: str = "ranged") -> bool:
        if not self.is_renegade_warband():
            return False
        if str(attack_type or "").strip().lower() != "ranged":
            return False
        _root, _source_member, source_sr, _bearer = self._renegade_warband_enhancement_source_member(
            unit,
            flag_key="enhancement_eyes_of_the_hunter",
            require_bearer_alive=True,
            require_bearer_on_battlefield=False,
        )
        if source_sr is None:
            return False
        if not bool(source_sr.get("enhancement_eyes_of_the_hunter_ignores_cover_ranged", False)):
            return False
        return True

    def renegade_warband_fratricidal_trophies_hit_reroll_active(self, unit: Unit, *, game=None) -> bool:
        if not self.is_renegade_warband():
            return False
        root, _source_member, source_sr, _bearer = self._renegade_warband_enhancement_source_member(
            unit,
            flag_key="enhancement_fratricidal_trophies",
            require_bearer_alive=True,
            require_bearer_on_battlefield=False,
        )
        if source_sr is None:
            return False
        if not bool(source_sr.get("enhancement_fratricidal_trophies_reroll_hit", False)):
            return False
        root_rules = getattr(root, "special_rules", {}) if root is not None else {}
        if bool(source_sr.get("enhancement_fratricidal_trophies_requires_default_to_doctrine", True)):
            if not self._renegade_warband_default_to_doctrine_active_state(root, game=game):
                return False
        return True

    def renegade_warband_empyric_symbiote_roll_bonus(self, unit: Unit, *, roll_kind: str) -> int:
        if not self.is_renegade_warband():
            return 0
        _root, _source_member, source_sr, _bearer = self._renegade_warband_enhancement_source_member(
            unit,
            flag_key="enhancement_empyric_symbiote",
            require_bearer_alive=True,
            require_bearer_on_battlefield=False,
        )
        if source_sr is None:
            return 0
        kind = str(roll_kind or "").strip().lower()
        if kind == "advance":
            value = source_sr.get("enhancement_empyric_symbiote_advance_roll_bonus", 1)
        elif kind == "charge":
            value = source_sr.get("enhancement_empyric_symbiote_charge_roll_bonus", 1)
        else:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def renegade_warband_empyric_symbiote_advance_roll_bonus(self, unit, *, game=None) -> tuple[int, str]:
        _ = game
        bonus = self.renegade_warband_empyric_symbiote_roll_bonus(unit, roll_kind="advance")
        if bonus <= 0:
            return 0, ""
        return int(bonus), self._RENEGADE_WARBAND_EMPYRIC_SYMBIOTE_SOURCE

    def renegade_warband_empyric_symbiote_charge_roll_bonus(self, unit, *, target_units=None, game=None) -> tuple[int, str]:
        _ = target_units
        _ = game
        bonus = self.renegade_warband_empyric_symbiote_roll_bonus(unit, roll_kind="charge")
        if bonus <= 0:
            return 0, ""
        return int(bonus), self._RENEGADE_WARBAND_EMPYRIC_SYMBIOTE_SOURCE

    def vendetta_reroll_hit_applies(self, attacker_model, target_unit, *, game=None) -> tuple[bool, str]:
        if not self.is_renegade_warband():
            return False, ""
        if attacker_model is None or target_unit is None:
            return False, ""
        if not self._model_in_army(attacker_model):
            return False, ""
        if not self._model_is_heretic_astartes(attacker_model):
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if self._unit_is_damned(attacker_unit):
            return False, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return False, ""
        stored_target_id = str(self.renegade_warband_vendetta_target_unit_id or "").strip()
        vendetta_active = False
        if stored_target_id and str(get_entity_id(target_root) or "") == stored_target_id:
            is_alive = getattr(target_root, "is_alive", None)
            vendetta_active = not (callable(is_alive) and not bool(is_alive()))
        if vendetta_active:
            return True, self._RENEGADE_WARBAND_VENDETTA_SOURCE
        if attacker_unit is not None and self.renegade_warband_fratricidal_trophies_hit_reroll_active(
            attacker_unit,
            game=game,
        ):
            return True, self._RENEGADE_WARBAND_FRATRICIDAL_TROPHIES_SOURCE
        return False, ""

    def clear_veterans_focus_of_hatred_target(self) -> None:
        self.veterans_focus_of_hatred_target_unit_id = ""

    def veterans_focus_of_hatred_candidate_enemy_units(self, *, game=None, player=None) -> list:
        if not self.is_veterans_of_the_long_war() or self.army is None:
            return []
        candidates: list = []
        for enemy_root in list(self._iter_enemy_units_for_player(game=game, player=player) or []):
            if self._unit_is_embarked(enemy_root):
                continue
            candidates.append(enemy_root)
        return candidates

    def _pending_veterans_focus_of_hatred_choice_request(self, game, *, army_id: str, battle_round: int) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != self._VETERANS_OF_THE_LONG_WAR_FOCUS_ABILITY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            try:
                ctx_round = int(ctx.get("battle_round", battle_round) or battle_round)
            except (TypeError, ValueError):
                ctx_round = int(battle_round or 0)
            if int(ctx_round) == int(battle_round):
                return True
        return False

    def can_select_veterans_focus_of_hatred_target(self, *, game=None, player=None) -> bool:
        if not self.is_veterans_of_the_long_war() or self.army is None:
            return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        army_player = getattr(self.army, "player", None)
        if army_player is not None:
            if str(getattr(army_player, "id", "") or "") != str(getattr(owner, "id", "") or ""):
                return False
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return False
        phase_name = self._current_phase_name(game=resolved_game)
        if phase_name and phase_name != "COMMAND_PHASE":
            return False
        current_owner = str(self._current_turn_owner_id(game=resolved_game, player=owner) or "")
        if current_owner and current_owner != str(getattr(owner, "id", "") or ""):
            return False
        return True

    def queue_veterans_focus_of_hatred_choice_request(self, *, game=None, player=None) -> None:
        if not self.is_veterans_of_the_long_war() or self.army is None:
            return
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None or not bool(getattr(resolved_game, "is_authoritative", True)):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        if not self.can_select_veterans_focus_of_hatred_target(game=resolved_game, player=owner):
            return

        self.clear_veterans_focus_of_hatred_target()

        candidates = list(self.veterans_focus_of_hatred_candidate_enemy_units(game=resolved_game, player=owner) or [])
        if not candidates:
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        army_id = str(get_entity_id(self.army) or "")
        battle_round = int(self._current_turn(game=resolved_game) or 0)
        if self._pending_veterans_focus_of_hatred_choice_request(
            resolved_game,
            army_id=army_id,
            battle_round=battle_round,
        ):
            return

        options: list[DecisionOption] = []
        candidate_ids: list[str] = []
        for unit in candidates:
            unit_id = str(get_entity_id(unit) or "")
            if not unit_id:
                continue
            candidate_ids.append(unit_id)
            options.append(
                DecisionOption.create(
                    str(getattr(unit, "name", "Enemy Unit") or "Enemy Unit"),
                    payload={
                        "target_unit_id": unit_id,
                        "army_id": army_id,
                    },
                )
            )
        if not options:
            return

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Focus of Hatred: select one enemy unit.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._VETERANS_OF_THE_LONG_WAR_FOCUS_ABILITY,
                "ability_name": self._VETERANS_OF_THE_LONG_WAR_FOCUS_SOURCE,
                "phase": "Command phase",
                "army_id": army_id,
                "battle_round": int(battle_round),
                "candidate_unit_ids": list(candidate_ids),
                "optional": False,
            },
        )
        if hasattr(resolved_game, "request_decision"):
            resolved_game.request_decision(request)

    def veterans_focus_of_hatred_target_is_valid(self, target_unit_id: str, *, game=None, player=None) -> bool:
        target_id = str(target_unit_id or "").strip()
        if not target_id:
            return False
        candidates = list(self.veterans_focus_of_hatred_candidate_enemy_units(game=game, player=player) or [])
        candidate_ids = {str(get_entity_id(unit) or "") for unit in candidates}
        return target_id in candidate_ids

    def select_veterans_focus_of_hatred_target(self, target_unit_id: str, *, game=None, player=None) -> dict:
        if not self.can_select_veterans_focus_of_hatred_target(game=game, player=player):
            return {"ok": False, "reason": "Focus of Hatred target cannot be selected right now."}
        target_id = str(target_unit_id or "").strip()
        if not self.veterans_focus_of_hatred_target_is_valid(target_id, game=game, player=player):
            return {"ok": False, "reason": "Focus of Hatred target is invalid."}
        self.veterans_focus_of_hatred_target_unit_id = target_id
        target_name = ""
        for unit in list(self.veterans_focus_of_hatred_candidate_enemy_units(game=game, player=player) or []):
            if str(get_entity_id(unit) or "") == target_id:
                target_name = str(getattr(unit, "name", "") or "").strip()
                break
        return {
            "ok": True,
            "target_unit_id": target_id,
            "target_name": target_name or "Enemy Unit",
            "source": self._VETERANS_OF_THE_LONG_WAR_FOCUS_SOURCE,
        }

    def _veterans_unit_by_id(self, unit_id: str):
        target_id = str(unit_id or "").strip()
        if not target_id or self.army is None:
            return None
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            if root is None:
                continue
            if str(get_entity_id(root) or "").strip() == target_id:
                return root
        return None

    def veterans_endless_ire_candidate_enemy_units(self, source_unit_id: str, *, game=None, player=None) -> list:
        if not self.is_veterans_of_the_long_war() or self.army is None:
            return []
        source_root = self._veterans_unit_by_id(source_unit_id)
        if source_root is None or not self._unit_on_battlefield(source_root):
            return []
        source_alive = getattr(source_root, "is_alive", None)
        if callable(source_alive) and not bool(source_alive()):
            return []
        if not self._unit_is_heretic_astartes(source_root):
            return []
        if self._unit_is_damned(source_root):
            return []
        if not self._unit_has_keyword(source_root, "CHARACTER"):
            return []

        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return []
        game_map = getattr(resolved_game, "map", None)
        los_checker = getattr(source_root, "_attacking_unit_has_any_los_to_target_unit", None)
        if game_map is None or not callable(los_checker):
            return []

        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except ImportError:
            return []

        owner = player if player is not None else getattr(self.army, "player", None)
        candidates: list = []
        for enemy_root in list(self._iter_enemy_units_for_player(game=resolved_game, player=owner) or []):
            if enemy_root is None or not self._unit_on_battlefield(enemy_root):
                continue
            enemy_alive = getattr(enemy_root, "is_alive", None)
            if callable(enemy_alive) and not bool(enemy_alive()):
                continue
            if not unit_within_range_of_unit(source_root, enemy_root, 12.0, use_attached_aggregate=True):
                continue
            if not bool(los_checker(enemy_root, game_map)):
                continue
            candidates.append(enemy_root)
        return sorted(self._iter_unique_roots(candidates), key=lambda unit: str(get_entity_id(unit) or self._unit_root_key(unit)))

    def veterans_endless_ire_target_is_valid(
        self,
        source_unit_id: str,
        target_unit_id: str,
        *,
        game=None,
        player=None,
    ) -> bool:
        target_id = str(target_unit_id or "").strip()
        if not target_id:
            return False
        candidates = list(
            self.veterans_endless_ire_candidate_enemy_units(source_unit_id, game=game, player=player) or []
        )
        candidate_ids = {str(get_entity_id(unit) or "").strip() for unit in candidates if unit is not None}
        return target_id in candidate_ids

    def select_veterans_endless_ire_target(
        self,
        source_unit_id: str,
        target_unit_id: str,
        *,
        game=None,
        player=None,
    ) -> dict:
        source_root = self._veterans_unit_by_id(source_unit_id)
        if source_root is None:
            return {"ok": False, "reason": "Endless Ire source unit was not found."}
        if not self.veterans_endless_ire_target_is_valid(source_unit_id, target_unit_id, game=game, player=player):
            return {"ok": False, "reason": "Endless Ire target is invalid."}

        target_id = str(target_unit_id or "").strip()
        self.veterans_focus_of_hatred_target_unit_id = target_id
        target_name = ""
        for unit in list(self.veterans_endless_ire_candidate_enemy_units(source_unit_id, game=game, player=player) or []):
            if str(get_entity_id(unit) or "").strip() == target_id:
                target_name = str(getattr(unit, "name", "") or "").strip()
                break
        return {
            "ok": True,
            "source_unit_id": str(get_entity_id(source_root) or "").strip(),
            "target_unit_id": target_id,
            "target_name": target_name or "Enemy Unit",
            "source": self._VETERANS_ENDLESS_IRE_SOURCE,
        }

    def veterans_focus_of_hatred_reroll_hit_applies(self, attacker_model, target_unit, *, game=None) -> tuple[bool, str]:
        if not self.is_veterans_of_the_long_war():
            return False, ""
        if attacker_model is None or target_unit is None:
            return False, ""
        if not self._model_in_army(attacker_model):
            return False, ""
        if not self._model_is_heretic_astartes(attacker_model):
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if self._unit_is_damned(attacker_unit):
            return False, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return False, ""
        if not self._veterans_focus_of_hatred_target_matches(target_root):
            return False, ""
        return True, self._VETERANS_OF_THE_LONG_WAR_FOCUS_SOURCE

    def _veterans_focus_of_hatred_target_matches(self, target_unit, *, require_alive: bool = True) -> bool:
        if not self.is_veterans_of_the_long_war():
            return False
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return False
        stored_target_id = str(self.veterans_focus_of_hatred_target_unit_id or "").strip()
        if not stored_target_id:
            return False
        if str(get_entity_id(target_root) or "") != stored_target_id and not self._unit_matches_split_origin(
            target_root,
            stored_target_id,
        ):
            return False
        if not require_alive:
            return True
        is_alive = getattr(target_root, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        return True

    def _veterans_enhancement_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_on_battlefield: bool = False,
    ):
        if not self.is_veterans_of_the_long_war():
            return None, None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None, None
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
                continue
            bearer = self._find_enhancement_bearer_on_member(member, sr)
            if require_bearer_alive and not self._model_alive(bearer):
                continue
            if require_bearer_on_battlefield:
                bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None)) if bearer is not None else root
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue
            return member, sr, bearer
        return None, None, None

    def _fellhammer_siege_host_enhancement_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_on_battlefield: bool = False,
    ):
        if not self.is_fellhammer_siege_host():
            return None, None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None, None
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
                continue
            bearer = self._find_enhancement_bearer_on_member(member, sr)
            if require_bearer_alive and not self._model_alive(bearer):
                continue
            if require_bearer_on_battlefield:
                bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None)) if bearer is not None else root
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue
            return member, sr, bearer
        return None, None, None

    def _dread_talons_enhancement_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_on_battlefield: bool = False,
    ):
        if not self.is_dread_talons():
            return None, None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None, None
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
                continue
            bearer = self._find_enhancement_bearer_on_member(member, sr)
            if require_bearer_alive and not self._model_alive(bearer):
                continue
            if require_bearer_on_battlefield:
                bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None)) if bearer is not None else root
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue
            return member, sr, bearer
        return None, None, None

    def _nightmare_hunt_enhancement_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_on_battlefield: bool = False,
    ):
        if not self.is_nightmare_hunt():
            return None, None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None, None
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
                continue
            bearer = self._find_enhancement_bearer_on_member(member, sr)
            if require_bearer_alive and not self._model_alive(bearer):
                continue
            if require_bearer_on_battlefield:
                bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None)) if bearer is not None else root
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue
            return member, sr, bearer
        return None, None, None

    def _hurons_marauders_enhancement_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_on_battlefield: bool = False,
    ):
        if not self.is_hurons_marauders():
            return None, None, None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None, None, None
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
                continue
            bearer = self._find_enhancement_bearer_on_member(member, sr)
            if require_bearer_alive and not self._model_alive(bearer):
                continue
            if require_bearer_on_battlefield:
                bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None)) if bearer is not None else root
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue
            return root, member, sr, bearer
        return None, None, None, None

    def _pactbound_zealots_enhancement_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_on_battlefield: bool = False,
    ):
        if not self.is_pactbound_zealots():
            return None, None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None, None
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
                continue
            bearer = self._find_enhancement_bearer_on_member(member, sr)
            if require_bearer_alive and not self._model_alive(bearer):
                continue
            if require_bearer_on_battlefield:
                bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None)) if bearer is not None else root
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue
            return member, sr, bearer
        return None, None, None

    def _cult_of_the_arkifane_enhancement_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_on_battlefield: bool = False,
    ):
        if not self.is_cult_of_the_arkifane():
            return None, None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None, None
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
                continue
            bearer = self._find_enhancement_bearer_on_member(member, sr)
            if require_bearer_alive and not self._model_alive(bearer):
                continue
            if require_bearer_on_battlefield:
                bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None)) if bearer is not None else root
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue
            return member, sr, bearer
        return None, None, None

    @staticmethod
    def _model_matches_bearer(model, bearer) -> bool:
        if model is None or bearer is None:
            return False
        if model is bearer:
            return True
        model_entity_id = str(get_entity_id(model) or "").strip()
        bearer_entity_id = str(get_entity_id(bearer) or "").strip()
        if model_entity_id and bearer_entity_id and model_entity_id == bearer_entity_id:
            return True
        model_local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
        bearer_local_id = str(getattr(bearer, "id", getattr(bearer, "_id", "")) or "").strip()
        if model_local_id and bearer_local_id and model_local_id == bearer_local_id:
            return True
        return False

    def veterans_eager_for_vengeance_hit_bonus(self, attacker_model, target_unit, *, game=None) -> tuple[int, str]:
        _ = game
        if not self.is_veterans_of_the_long_war():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        if not self._model_in_army(attacker_model):
            return 0, ""
        attacker_root = self._unit_root(getattr(attacker_model, "parent_unit", None))
        if attacker_root is None:
            return 0, ""
        _source_member, source_sr, _bearer = self._veterans_enhancement_source_member(
            attacker_root,
            flag_key="enhancement_eager_for_vengeance",
            require_bearer_alive=True,
            require_bearer_on_battlefield=True,
        )
        if source_sr is None:
            return 0, ""
        if bool(source_sr.get("enhancement_eager_for_vengeance_requires_focus_of_hatred_target", True)):
            if not self._veterans_focus_of_hatred_target_matches(target_unit):
                return 0, ""
        if bool(source_sr.get("enhancement_eager_for_vengeance_requires_fell_back_this_turn", True)):
            fell_back = bool(getattr(getattr(attacker_root, "round_state", None), "fell_back_this_round", False))
            if not fell_back:
                return 0, ""
        try:
            bonus = int(source_sr.get("enhancement_eager_for_vengeance_hit_roll_bonus", 1) or 0)
        except (TypeError, ValueError):
            bonus = 0
        if bonus <= 0:
            return 0, ""
        source = str(source_sr.get("enhancement_eager_for_vengeance_source", "") or "Eager for Vengeance").strip()
        return int(bonus), (source or "Eager for Vengeance")

    def veterans_eager_for_vengeance_can_shoot_after_fall_back(self, unit, profile=None, *, game=None) -> bool:
        _ = game
        root = self._unit_root(unit)
        if root is None:
            return False
        _source_member, source_sr, _bearer = self._veterans_enhancement_source_member(
            root,
            flag_key="enhancement_eager_for_vengeance",
            require_bearer_alive=True,
            require_bearer_on_battlefield=True,
        )
        if source_sr is None:
            return False
        if not bool(source_sr.get("enhancement_eager_for_vengeance_allow_shoot_after_fall_back", True)):
            return False
        parent = getattr(profile, "parent_wargear", None) if profile is not None else None
        is_ranged = getattr(parent, "is_ranged", None) if parent is not None else None
        if callable(is_ranged):
            return bool(is_ranged())
        return True

    def veterans_eager_for_vengeance_can_charge_after_fall_back(self, unit, *, game=None) -> bool:
        _ = game
        root = self._unit_root(unit)
        if root is None:
            return False
        _source_member, source_sr, _bearer = self._veterans_enhancement_source_member(
            root,
            flag_key="enhancement_eager_for_vengeance",
            require_bearer_alive=True,
            require_bearer_on_battlefield=True,
        )
        if source_sr is None:
            return False
        return bool(source_sr.get("enhancement_eager_for_vengeance_allow_charge_after_fall_back", True))

    def veterans_eager_for_vengeance_charge_roll_bonus(self, unit, *, target_units=None, game=None) -> tuple[int, str]:
        _ = game
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        _source_member, source_sr, _bearer = self._veterans_enhancement_source_member(
            root,
            flag_key="enhancement_eager_for_vengeance",
            require_bearer_alive=True,
            require_bearer_on_battlefield=True,
        )
        if source_sr is None:
            return 0, ""
        if bool(source_sr.get("enhancement_eager_for_vengeance_requires_fell_back_this_turn", True)):
            fell_back = bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False))
            if not fell_back:
                return 0, ""
        if bool(source_sr.get("enhancement_eager_for_vengeance_requires_focus_of_hatred_target", True)):
            targets = []
            if target_units is None:
                targets = []
            elif isinstance(target_units, (list, tuple, set)):
                targets = list(target_units)
            else:
                targets = [target_units]
            if not any(self._veterans_focus_of_hatred_target_matches(target) for target in targets):
                return 0, ""
        try:
            bonus = int(source_sr.get("enhancement_eager_for_vengeance_charge_roll_bonus", 1) or 0)
        except (TypeError, ValueError):
            bonus = 0
        if bonus <= 0:
            return 0, ""
        source = str(source_sr.get("enhancement_eager_for_vengeance_source", "") or "Eager for Vengeance").strip()
        return int(bonus), (source or "Eager for Vengeance")

    def veterans_warmasters_gift_crit_wound_threshold(
        self,
        attacker_model,
        target_unit,
        *,
        game=None,
    ) -> tuple[int, str]:
        _ = game
        if not self.is_veterans_of_the_long_war():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        if not self._model_in_army(attacker_model):
            return 0, ""
        attacker_root = self._unit_root(getattr(attacker_model, "parent_unit", None))
        if attacker_root is None:
            return 0, ""
        _source_member, source_sr, bearer = self._veterans_enhancement_source_member(
            attacker_root,
            flag_key="enhancement_warmasters_gift",
            require_bearer_alive=True,
            require_bearer_on_battlefield=True,
        )
        if source_sr is None or bearer is None:
            return 0, ""
        if not self._model_matches_bearer(attacker_model, bearer):
            return 0, ""
        if bool(source_sr.get("enhancement_warmasters_gift_requires_focus_of_hatred_target", True)):
            if not self._veterans_focus_of_hatred_target_matches(target_unit):
                return 0, ""
        try:
            threshold = int(source_sr.get("enhancement_warmasters_gift_crit_wound_threshold", 5) or 0)
        except (TypeError, ValueError):
            threshold = 0
        if threshold <= 0:
            return 0, ""
        threshold = int(min(6, max(2, threshold)))
        source = str(source_sr.get("enhancement_warmasters_gift_source", "") or "Warmaster's Gift").strip()
        return threshold, (source or "Warmaster's Gift")

    def _veterans_mark_of_legend_source_for_model(self, model):
        if model is None or not self._model_in_army(model):
            return None, None, None
        root = self._unit_root(getattr(model, "parent_unit", None))
        if root is None:
            return None, None, None
        source_member, source_sr, bearer = self._veterans_enhancement_source_member(
            root,
            flag_key="enhancement_mark_of_legend",
            require_bearer_alive=True,
            require_bearer_on_battlefield=False,
        )
        if source_sr is None or bearer is None:
            return None, None, None
        if not self._model_matches_bearer(model, bearer):
            return None, None, None
        return source_member, source_sr, bearer

    def _veterans_mark_of_legend_usage_key(self, *, game=None) -> tuple[int, str]:
        turn = int(self._current_turn(game=game) or 0)
        owner = str(self._current_turn_owner_id(game=game) or "")
        return int(turn), owner

    def _veterans_mark_of_legend_reroll_available(self, model, *, game=None, roll_type: str) -> tuple[bool, str]:
        source_member, source_sr, _bearer = self._veterans_mark_of_legend_source_for_model(model)
        if source_member is None or source_sr is None:
            return False, ""
        allow_key = f"enhancement_mark_of_legend_allow_{str(roll_type or '').strip().lower()}_reroll"
        if not bool(source_sr.get(allow_key, True)):
            return False, ""
        if bool(source_sr.get("enhancement_mark_of_legend_once_per_turn", True)):
            current_turn, current_owner = self._veterans_mark_of_legend_usage_key(game=game)
            try:
                used_turn = int(source_sr.get("enhancement_mark_of_legend_last_used_turn", 0) or 0)
            except (TypeError, ValueError):
                used_turn = 0
            used_owner = str(source_sr.get("enhancement_mark_of_legend_last_used_turn_owner", "") or "")
            if used_turn and used_turn == int(current_turn) and used_owner == str(current_owner):
                return False, ""
        source = str(source_sr.get("enhancement_mark_of_legend_source", "") or "Mark of Legend").strip()
        return True, (source or "Mark of Legend")

    def veterans_mark_of_legend_reroll_hit_available(self, attacker_model, *, game=None) -> tuple[bool, str]:
        return self._veterans_mark_of_legend_reroll_available(attacker_model, game=game, roll_type="hit")

    def veterans_mark_of_legend_reroll_wound_available(self, attacker_model, *, game=None) -> tuple[bool, str]:
        return self._veterans_mark_of_legend_reroll_available(attacker_model, game=game, roll_type="wound")

    def veterans_mark_of_legend_reroll_save_available(self, target_model, *, game=None) -> tuple[bool, str]:
        return self._veterans_mark_of_legend_reroll_available(target_model, game=game, roll_type="save")

    def veterans_mark_of_legend_consume_reroll(self, model, *, roll_type: str, game=None) -> bool:
        source_member, source_sr, _bearer = self._veterans_mark_of_legend_source_for_model(model)
        if source_member is None or source_sr is None:
            return False
        allowed, _source = self._veterans_mark_of_legend_reroll_available(
            model,
            game=game,
            roll_type=roll_type,
        )
        if not allowed:
            return False
        current_turn, current_owner = self._veterans_mark_of_legend_usage_key(game=game)
        source_sr["enhancement_mark_of_legend_last_used_turn"] = int(current_turn)
        source_sr["enhancement_mark_of_legend_last_used_turn_owner"] = str(current_owner)
        source_sr["enhancement_mark_of_legend_last_used_roll_type"] = str(roll_type or "").strip().lower()
        source_member.special_rules = source_sr
        self._clear_unit_ability_cache(self._unit_root(getattr(model, "parent_unit", None)))
        return True

    def veterans_eye_of_abaddon_on_focus_destroyed(self, destroyed_unit, *, game=None) -> dict:
        if not self.is_veterans_of_the_long_war() or self.army is None:
            return {}
        if destroyed_unit is None:
            return {}
        if not self._veterans_focus_of_hatred_target_matches(destroyed_unit, require_alive=False):
            return {}
        owner = getattr(self.army, "player", None)
        gain_cp = getattr(owner, "gain_command_points", None) if owner is not None else None
        if not callable(gain_cp):
            return {}
        roots = list(self._iter_unique_roots(getattr(self.army, "units", []) or []))
        roots.sort(key=lambda unit: str(get_entity_id(unit) or self._unit_root_key(unit)))
        for root in roots:
            _source_member, source_sr, bearer = self._veterans_enhancement_source_member(
                root,
                flag_key="enhancement_eye_of_abaddon",
                require_bearer_alive=True,
                require_bearer_on_battlefield=False,
            )
            if source_sr is None:
                continue
            if bool(source_sr.get("enhancement_eye_of_abaddon_requires_bearer_on_battlefield", True)):
                bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None)) if bearer is not None else None
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue
            source = str(source_sr.get("enhancement_eye_of_abaddon_source", "") or "Eye of Abaddon").strip() or "Eye of Abaddon"
            try:
                success_on = int(source_sr.get("enhancement_eye_of_abaddon_success_on", 4) or 4)
            except (TypeError, ValueError):
                success_on = 4
            success_on = int(min(6, max(2, success_on)))
            try:
                cp_gain = int(source_sr.get("enhancement_eye_of_abaddon_cp_gain", 1) or 1)
            except (TypeError, ValueError):
                cp_gain = 1
            cp_gain = int(max(1, cp_gain))
            roll = int(get_roll("D6"))
            gained = 0
            if roll >= success_on:
                gained = int(gain_cp(cp_gain, reason=source) or 0)
            return {
                "triggered": True,
                "source": source,
                "roll": int(roll),
                "success_on": int(success_on),
                "cp_gain": int(cp_gain),
                "gained": int(gained),
                "focus_unit_id": str(get_entity_id(self._unit_root(destroyed_unit)) or ""),
                "source_unit_id": str(get_entity_id(root) or ""),
                "source_model_id": str(get_entity_id(bearer) or "") if bearer is not None else "",
            }
        return {}

    def _veterans_effect_state(
        self,
        unit,
        *,
        prefix: str,
        game=None,
        require_phase_match: bool = True,
    ):
        if not self.is_veterans_of_the_long_war():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None, None
        if not bool(sr.get(f"{prefix}_active", False)):
            return None, None

        expected_phase = str(sr.get(f"{prefix}_phase", "") or "").strip().upper()
        expected_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if require_phase_match and expected_phase and current_phase and expected_phase != current_phase:
            return None, None
        if expected_owner and current_owner and expected_owner != current_owner:
            return None, None
        if expected_turn and current_turn and expected_turn != current_turn:
            return None, None
        return root, sr

    def _set_veterans_effect_state(
        self,
        unit,
        *,
        prefix: str,
        source: str,
        player=None,
        game=None,
        extra_state: Optional[dict] = None,
        track_phase: bool = True,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        if track_phase:
            sr[f"{prefix}_phase"] = self._current_phase_name(game=game)
        else:
            sr.pop(f"{prefix}_phase", None)
        sr[f"{prefix}_turn"] = self._current_turn(game=game)
        sr[f"{prefix}_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr[f"{prefix}_source"] = str(source or "").strip() or str(prefix).replace("_", " ").title()
        for key, value in dict(extra_state or {}).items():
            sr[str(key)] = value
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

    @staticmethod
    def _veterans_effect_source(sr: dict, *, prefix: str, default: str) -> str:
        if not isinstance(sr, dict):
            return str(default or "").strip()
        return str(sr.get(f"{prefix}_source", "") or default).strip() or str(default or "").strip()

    @staticmethod
    def _veterans_weapon_name(weapon_profile) -> str:
        parent = getattr(weapon_profile, "parent_wargear", None) if weapon_profile is not None else None
        return str(getattr(parent, "name", "") or getattr(weapon_profile, "name", "") or "").strip()

    @staticmethod
    def _veterans_normalize_weapon_name(name: str) -> str:
        return "".join(ch for ch in str(name or "").lower() if ch.isalnum())

    @classmethod
    def _veterans_black_crusade_weapon_is_eligible(cls, weapon_profile) -> bool:
        if weapon_profile is None:
            return False
        weapon_name = cls._veterans_normalize_weapon_name(cls._veterans_weapon_name(weapon_profile))
        return weapon_name in {"boltpistol", "boltgun", "combibolter"}

    def veterans_black_crusade_can_shoot_after_advance(self, unit, profile=None, *, game=None) -> bool:
        if profile is not None and not self._weapon_profile_matches_attack_type(profile, "ranged"):
            return False
        root, _sr = self._veterans_effect_state(
            unit,
            prefix=self._VETERANS_BLACK_CRUSADE_PREFIX,
            game=game,
            require_phase_match=False,
        )
        return bool(root is not None and self._unit_is_heretic_astartes(root) and not self._unit_is_damned(root))

    def veterans_black_crusade_can_shoot_after_fall_back(self, unit, profile=None, *, game=None) -> bool:
        if profile is not None and not self._weapon_profile_matches_attack_type(profile, "ranged"):
            return False
        root, _sr = self._veterans_effect_state(
            unit,
            prefix=self._VETERANS_BLACK_CRUSADE_PREFIX,
            game=game,
            require_phase_match=False,
        )
        return bool(root is not None and self._unit_is_heretic_astartes(root) and not self._unit_is_damned(root))

    def veterans_black_crusade_devastating_wounds_applies(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged"):
            return False, ""
        if not self._veterans_black_crusade_weapon_is_eligible(weapon_profile):
            return False, ""
        attacker_root, sr = self._veterans_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._VETERANS_BLACK_CRUSADE_PREFIX,
            game=game,
            require_phase_match=False,
        )
        if attacker_root is None or not self._unit_is_heretic_astartes(attacker_root):
            return False, ""
        if self._unit_is_damned(attacker_root):
            return False, ""
        try:
            damage_cap = int(sr.get(self._VETERANS_BLACK_CRUSADE_DAMAGE_CAP_KEY, 6) or 6)
        except (TypeError, ValueError):
            damage_cap = 6
        try:
            current_damage = int(sr.get(self._VETERANS_BLACK_CRUSADE_DAMAGE_KEY, 0) or 0)
        except (TypeError, ValueError):
            current_damage = 0
        if current_damage >= max(1, damage_cap):
            return False, ""
        return True, self._veterans_effect_source(
            sr,
            prefix=self._VETERANS_BLACK_CRUSADE_PREFIX,
            default=self._VETERANS_BLACK_CRUSADE_SOURCE,
        )

    def veterans_record_black_crusade_damage(self, attacker_model, damage_applied: int, *, game=None) -> int:
        if attacker_model is None:
            return 0
        try:
            damage_value = int(damage_applied or 0)
        except (TypeError, ValueError):
            damage_value = 0
        if damage_value <= 0:
            return 0
        attacker_root, sr = self._veterans_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._VETERANS_BLACK_CRUSADE_PREFIX,
            game=game,
            require_phase_match=False,
        )
        if attacker_root is None or not isinstance(sr, dict):
            return 0
        try:
            current_damage = int(sr.get(self._VETERANS_BLACK_CRUSADE_DAMAGE_KEY, 0) or 0)
        except (TypeError, ValueError):
            current_damage = 0
        sr[self._VETERANS_BLACK_CRUSADE_DAMAGE_KEY] = int(max(0, current_damage + damage_value))
        attacker_root.special_rules = sr
        self._clear_unit_ability_cache(attacker_root)
        return int(damage_value)

    def veterans_let_the_galaxy_burn_ignores_cover_active(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged"):
            return False, ""
        attacker_root, sr = self._veterans_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._VETERANS_LET_THE_GALAXY_BURN_PREFIX,
            game=game,
        )
        if attacker_root is None or not self._unit_is_heretic_astartes(attacker_root):
            return False, ""
        return True, self._veterans_effect_source(
            sr,
            prefix=self._VETERANS_LET_THE_GALAXY_BURN_PREFIX,
            default=self._VETERANS_LET_THE_GALAXY_BURN_SOURCE,
        )

    def veterans_let_the_galaxy_burn_torrent_attacks_override(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged"):
            return 0, ""
        if not bool(getattr(weapon_profile, "is_torrent", lambda: False)()):
            return 0, ""
        attacker_root, sr = self._veterans_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._VETERANS_LET_THE_GALAXY_BURN_PREFIX,
            game=game,
        )
        if attacker_root is None or not self._unit_is_heretic_astartes(attacker_root):
            return 0, ""
        try:
            attacks_value = int(
                sr.get(f"{self._VETERANS_LET_THE_GALAXY_BURN_PREFIX}_torrent_attacks", 6) or 6
            )
        except (TypeError, ValueError):
            attacks_value = 6
        if attacks_value <= 0:
            return 0, ""
        return int(attacks_value), self._veterans_effect_source(
            sr,
            prefix=self._VETERANS_LET_THE_GALAXY_BURN_PREFIX,
            default=self._VETERANS_LET_THE_GALAXY_BURN_SOURCE,
        )

    def veterans_bringers_of_despair_fight_first_active(self, unit, *, game=None) -> tuple[bool, str]:
        root, sr = self._veterans_effect_state(
            unit,
            prefix=self._VETERANS_BRINGERS_OF_DESPAIR_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        if self._unit_is_damned(root):
            return False, ""
        return True, self._veterans_effect_source(
            sr,
            prefix=self._VETERANS_BRINGERS_OF_DESPAIR_PREFIX,
            default=self._VETERANS_BRINGERS_OF_DESPAIR_SOURCE,
        )

    def dread_talons_eater_of_dread_on_command_phase_start(self, *, game=None) -> list[dict]:
        if not self.is_dread_talons() or self.army is None:
            return []
        owner = getattr(self.army, "player", None)
        gain_cp = getattr(owner, "gain_command_points", None) if owner is not None else None
        if not callable(gain_cp):
            return []

        enemy_units = [
            unit
            for unit in list(self._iter_enemy_units_for_player(game=game, player=owner) or [])
            if self._unit_on_battlefield(unit)
        ]
        battle_shocked_enemy_count = int(sum(1 for unit in enemy_units if self._unit_is_battle_shocked(unit)))

        roots = list(self._iter_unique_roots(getattr(self.army, "units", []) or []))
        roots.sort(key=lambda unit: str(get_entity_id(unit) or self._unit_root_key(unit)))

        out: list[dict] = []
        for root in roots:
            _source_member, source_sr, bearer = self._dread_talons_enhancement_source_member(
                root,
                flag_key="enhancement_eater_of_dread",
                require_bearer_alive=True,
                require_bearer_on_battlefield=False,
            )
            if source_sr is None:
                continue
            if bool(source_sr.get("enhancement_eater_of_dread_requires_bearer_on_battlefield", True)):
                bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None)) if bearer is not None else None
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue

            source = (
                str(source_sr.get("enhancement_eater_of_dread_source", "") or "Eater of Dread").strip()
                or "Eater of Dread"
            )
            try:
                success_on = int(source_sr.get("enhancement_eater_of_dread_success_on", 5) or 5)
            except (TypeError, ValueError):
                success_on = 5
            success_on = int(min(6, max(2, success_on)))
            try:
                cp_gain = int(source_sr.get("enhancement_eater_of_dread_cp_gain", 1) or 1)
            except (TypeError, ValueError):
                cp_gain = 1
            cp_gain = int(max(1, cp_gain))
            try:
                bonus_per_enemy = int(source_sr.get("enhancement_eater_of_dread_enemy_battleshocked_roll_bonus", 1) or 1)
            except (TypeError, ValueError):
                bonus_per_enemy = 1
            bonus_per_enemy = int(max(0, bonus_per_enemy))

            roll = int(get_roll("D6"))
            modifier = int(bonus_per_enemy * battle_shocked_enemy_count)
            total = int(roll + modifier)
            gained = 0
            if total >= success_on:
                gained = int(gain_cp(cp_gain, reason=source) or 0)

            out.append(
                {
                    "triggered": True,
                    "source": source,
                    "roll": int(roll),
                    "roll_modifier": int(modifier),
                    "battle_shocked_enemy_count": int(battle_shocked_enemy_count),
                    "total": int(total),
                    "success_on": int(success_on),
                    "cp_gain": int(cp_gain),
                    "gained": int(gained),
                    "source_unit_id": str(get_entity_id(root) or ""),
                    "source_model_id": str(get_entity_id(bearer) or "") if bearer is not None else "",
                }
            )
        return out

    def _soulforged_sources_by_flag(
        self,
        *,
        flag_key: str,
        require_alive_bearer: bool = True,
        require_bearer_on_battlefield: bool = True,
    ) -> list[tuple]:
        if not self.is_soulforged_warpack() or self.army is None:
            return []
        out: list[tuple] = []
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            if root is None or not self._unit_in_army(root):
                continue
            get_members = getattr(root, "get_attached_unit_members", None)
            members = list(get_members() or []) if callable(get_members) else [root]
            if not members:
                members = [root]
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict) or not bool(sr.get(flag_key, False)):
                    continue
                bearer = self._find_enhancement_bearer_on_member(member, sr)
                if bool(require_alive_bearer) and not self._model_alive(bearer):
                    continue
                if bool(require_bearer_on_battlefield):
                    bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None))
                    if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                        continue
                out.append((root, member, sr, bearer))
                break
        out.sort(
            key=lambda entry: (
                str(get_entity_id(entry[0]) or self._unit_root_key(entry[0])),
                str(get_entity_id(entry[3]) or ""),
            )
        )
        return out

    def _soulforged_source_entry(self, source_unit_id: str, *, flag_key: str):
        target_id = str(source_unit_id or "").strip()
        if not target_id:
            return None
        for entry in self._soulforged_sources_by_flag(flag_key=flag_key):
            root = entry[0]
            if str(get_entity_id(root) or "") == target_id:
                return entry
        return None

    def _soulforged_forges_blessing_effect_active(self, source_sr: dict, *, game=None) -> bool:
        if not isinstance(source_sr, dict):
            return False
        if not str(source_sr.get("enhancement_forges_blessing_target_unit_id", "") or "").strip():
            return False
        current_phase = self._current_phase_name(game=game)
        current_owner = str(self._current_turn_owner_id(game=game) or "")
        current_turn = int(self._current_turn(game=game) or 0)
        selected_owner = str(source_sr.get("enhancement_forges_blessing_turn_owner_id", "") or "")
        try:
            selected_turn = int(source_sr.get("enhancement_forges_blessing_turn", 0) or 0)
        except (TypeError, ValueError):
            selected_turn = 0
        if (
            current_phase == "COMMAND_PHASE"
            and selected_owner
            and current_owner == selected_owner
            and selected_turn
            and current_turn
            and current_turn != selected_turn
        ):
            return False
        return True

    def can_select_soulforged_forges_blessing(self, *, game=None, player=None) -> bool:
        if not self.is_soulforged_warpack() or self.army is None:
            return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        army_player = getattr(self.army, "player", None)
        if army_player is not None:
            if str(getattr(army_player, "id", "") or "") != str(getattr(owner, "id", "") or ""):
                return False
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return False
        phase_name = self._current_phase_name(game=resolved_game)
        if phase_name and phase_name != "COMMAND_PHASE":
            return False
        current_owner = str(self._current_turn_owner_id(game=resolved_game, player=owner) or "")
        if current_owner and current_owner != str(getattr(owner, "id", "") or ""):
            return False
        return True

    def soulforged_forges_blessing_candidate_units(self, source_unit_id: str, *, game=None, player=None) -> list[dict]:
        if not self.is_soulforged_warpack() or self.army is None:
            return []
        _ = player
        entry = self._soulforged_source_entry(source_unit_id, flag_key="enhancement_forges_blessing")
        if entry is None:
            return []
        _source_root, _source_member, source_sr, source_bearer = entry
        if source_sr is None or source_bearer is None or not self._model_alive(source_bearer):
            return []
        from ..utility.aura_utils import model_within_range_of_unit

        try:
            range_in = float(source_sr.get("enhancement_forges_blessing_range", 12.0) or 12.0)
        except (TypeError, ValueError):
            range_in = 12.0
        if range_in < 0:
            range_in = 0.0
        required_keyword = str(
            source_sr.get("enhancement_forges_blessing_target_requires_keyword", "VEHICLE") or "VEHICLE"
        ).strip().upper()
        required_faction_keyword = str(
            source_sr.get("enhancement_forges_blessing_target_requires_faction_keyword", "HERETIC ASTARTES")
            or "HERETIC ASTARTES"
        ).strip().upper()

        out: list[dict] = []
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            if root is None or not self._unit_in_army(root):
                continue
            if not self._unit_on_battlefield(root):
                continue
            if required_keyword and not self._unit_has_keyword(root, required_keyword):
                continue
            if required_faction_keyword and not self._unit_has_keyword(root, required_faction_keyword):
                continue
            if not bool(model_within_range_of_unit(source_bearer, root, range_in, use_attached_aggregate=True)):
                continue
            unit_id = str(get_entity_id(root) or "")
            if not unit_id:
                continue
            out.append(
                {
                    "target_unit_id": unit_id,
                    "target_unit_name": str(getattr(root, "name", "Unit") or "Unit"),
                }
            )
        out.sort(key=lambda item: str(item.get("target_unit_id", "")))
        return out

    def queue_soulforged_forges_blessing_choice_request(self, *, game=None, player=None) -> None:
        if not self.is_soulforged_warpack() or self.army is None:
            return
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None or not bool(getattr(resolved_game, "is_authoritative", True)):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        if not self.can_select_soulforged_forges_blessing(game=resolved_game, player=owner):
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        army_id = str(get_entity_id(self.army) or "")
        for source_root, _source_member, source_sr, source_bearer in self._soulforged_sources_by_flag(
            flag_key="enhancement_forges_blessing"
        ):
            source_unit_id = str(get_entity_id(source_root) or "")
            if not source_unit_id:
                continue
            if self._pending_deceptors_choose_quarry_request(
                resolved_game,
                ability=self._SOULFORGED_WARPACK_FORGES_BLESSING_ABILITY,
                army_id=army_id,
                source_unit_id=source_unit_id,
            ):
                continue
            candidates = list(
                self.soulforged_forges_blessing_candidate_units(
                    source_unit_id,
                    game=resolved_game,
                    player=owner,
                )
                or []
            )
            if not candidates:
                continue
            options: list[DecisionOption] = []
            candidate_ids: list[str] = []
            for candidate in candidates:
                target_unit_id = str(candidate.get("target_unit_id", "") or "").strip()
                if not target_unit_id:
                    continue
                candidate_ids.append(target_unit_id)
                options.append(
                    DecisionOption.create(
                        str(candidate.get("target_unit_name", "Unit") or "Unit"),
                        payload={
                            "source_unit_id": source_unit_id,
                            "target_unit_id": target_unit_id,
                            "army_id": army_id,
                        },
                    )
                )
            if not options:
                continue
            try:
                range_in = float(source_sr.get("enhancement_forges_blessing_range", 12.0) or 12.0)
            except (TypeError, ValueError):
                range_in = 12.0
            source_model_id = str(get_entity_id(source_bearer) or "")
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Forge's Blessing: select one friendly HERETIC ASTARTES VEHICLE unit within 12\" of the bearer.",
                player_id=getattr(owner, "id", None),
                options=options,
                context={
                    "ability": self._SOULFORGED_WARPACK_FORGES_BLESSING_ABILITY,
                    "ability_name": self._SOULFORGED_WARPACK_FORGES_BLESSING_SOURCE,
                    "phase": "Command phase",
                    "army_id": army_id,
                    "source_unit_id": source_unit_id,
                    "source_model_id": source_model_id,
                    "candidate_unit_ids": list(candidate_ids),
                    "range": float(max(0.0, range_in)),
                    "optional": False,
                },
            )
            if hasattr(resolved_game, "request_decision"):
                resolved_game.request_decision(request)

    def soulforged_forges_blessing_target_is_valid(
        self,
        source_unit_id: str,
        target_unit_id: str,
        *,
        game=None,
        player=None,
    ) -> bool:
        target_id = str(target_unit_id or "").strip()
        if not target_id:
            return False
        candidates = list(self.soulforged_forges_blessing_candidate_units(source_unit_id, game=game, player=player) or [])
        candidate_ids = {str(item.get("target_unit_id", "") or "").strip() for item in candidates}
        return target_id in candidate_ids

    def select_soulforged_forges_blessing_target(
        self,
        source_unit_id: str,
        target_unit_id: str,
        *,
        game=None,
        player=None,
    ) -> dict:
        if not self.can_select_soulforged_forges_blessing(game=game, player=player):
            return {"ok": False, "reason": "Forge's Blessing target cannot be selected right now."}
        entry = self._soulforged_source_entry(source_unit_id, flag_key="enhancement_forges_blessing")
        if entry is None:
            return {"ok": False, "reason": "Forge's Blessing source unit was not found."}
        source_root, source_member, source_sr, _source_bearer = entry
        if not isinstance(source_sr, dict):
            return {"ok": False, "reason": "Forge's Blessing source state is unavailable."}
        target_id = str(target_unit_id or "").strip()
        if not self.soulforged_forges_blessing_target_is_valid(source_unit_id, target_id, game=game, player=player):
            return {"ok": False, "reason": "Forge's Blessing target is invalid."}
        updated = dict(source_sr)
        updated["enhancement_forges_blessing_target_unit_id"] = target_id
        updated["enhancement_forges_blessing_turn"] = int(self._current_turn(game=game) or 0)
        updated["enhancement_forges_blessing_turn_owner_id"] = str(
            self._current_turn_owner_id(game=game, player=player) or ""
        )
        source_member.special_rules = updated
        target_name = "Unit"
        for candidate in list(self.soulforged_forges_blessing_candidate_units(source_unit_id, game=game, player=player) or []):
            if str(candidate.get("target_unit_id", "") or "") == target_id:
                target_name = str(candidate.get("target_unit_name", "Unit") or "Unit")
                break
        return {
            "ok": True,
            "source_unit_id": str(get_entity_id(source_root) or ""),
            "target_unit_id": target_id,
            "target_name": target_name,
            "source": str(
                updated.get("enhancement_forges_blessing_source", "")
                or self._SOULFORGED_WARPACK_FORGES_BLESSING_SOURCE
            ).strip()
            or self._SOULFORGED_WARPACK_FORGES_BLESSING_SOURCE,
        }

    def soulforged_forges_blessing_fnp(self, unit, *, target_model=None, game=None) -> tuple[int, str]:
        _ = target_model
        if not self.is_soulforged_warpack():
            return 0, ""
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return 0, ""
        target_unit_id = str(get_entity_id(root) or "")
        if not target_unit_id:
            return 0, ""
        best_value = 0
        best_source = ""
        for _source_root, _source_member, source_sr, _source_bearer in self._soulforged_sources_by_flag(
            flag_key="enhancement_forges_blessing",
            require_alive_bearer=False,
            require_bearer_on_battlefield=False,
        ):
            if source_sr is None:
                continue
            selected_target_id = str(source_sr.get("enhancement_forges_blessing_target_unit_id", "") or "").strip()
            if not selected_target_id or selected_target_id != target_unit_id:
                continue
            if not self._soulforged_forges_blessing_effect_active(source_sr, game=game):
                continue
            try:
                fnp_value = int(source_sr.get("enhancement_forges_blessing_fnp", 6) or 6)
            except (TypeError, ValueError):
                fnp_value = 6
            fnp_value = max(2, min(6, fnp_value))
            source = str(
                source_sr.get("enhancement_forges_blessing_source", "")
                or self._SOULFORGED_WARPACK_FORGES_BLESSING_SOURCE
            ).strip() or self._SOULFORGED_WARPACK_FORGES_BLESSING_SOURCE
            if best_value == 0 or fnp_value < best_value:
                best_value = fnp_value
                best_source = source
        if best_value <= 0:
            return 0, ""
        return int(best_value), best_source

    def _soulforged_tempting_addendum_source_for_unit(self, unit, *, game=None) -> tuple[dict | None, str]:
        if not self.is_soulforged_warpack():
            return None, ""
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, ""
        if not self._unit_is_daemon_vehicle(root):
            return None, ""
        from ..utility.aura_utils import model_within_range_of_unit

        for _source_root, _source_member, source_sr, source_bearer in self._soulforged_sources_by_flag(
            flag_key="enhancement_tempting_addendum"
        ):
            if source_sr is None or source_bearer is None:
                continue
            try:
                range_in = float(source_sr.get("enhancement_tempting_addendum_range", 3.0) or 3.0)
            except (TypeError, ValueError):
                range_in = 3.0
            if range_in < 0:
                range_in = 0.0
            if not bool(model_within_range_of_unit(source_bearer, root, range_in, use_attached_aggregate=True)):
                continue
            source = str(
                source_sr.get("enhancement_tempting_addendum_source", "")
                or self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_SOURCE
            ).strip() or self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_SOURCE
            return source_sr, source
        return None, ""

    def soulforged_warpack_tempting_addendum_for_invoked_contract(self, unit, *, game=None) -> tuple[bool, str, int, bool]:
        source_sr, source = self._soulforged_tempting_addendum_source_for_unit(unit, game=game)
        if source_sr is None:
            return False, "", 0, False
        try:
            mortal_bonus = int(
                source_sr.get("enhancement_tempting_addendum_dark_pact_failure_mortal_wound_bonus", 1) or 1
            )
        except (TypeError, ValueError):
            mortal_bonus = 1
        mortal_bonus = max(0, mortal_bonus)
        reroll_hit = bool(source_sr.get("enhancement_tempting_addendum_reroll_hit", True))
        return True, source, int(mortal_bonus), reroll_hit

    def _soulforged_warpack_tempting_addendum_state(self, unit, *, game=None) -> tuple[bool, str]:
        if not self.is_soulforged_warpack():
            return False, ""
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False, ""
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False, ""
        if not bool(sr.get(self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_ACTIVE_KEY, False)):
            return False, ""
        expected_phase = str(sr.get(self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_EXPIRES_PHASE_KEY, "") or "").strip().upper()
        current_phase = self._current_phase_name(game=game)
        if expected_phase and current_phase and expected_phase != current_phase:
            return False, ""
        expected_owner = str(sr.get(self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_OWNER_KEY, "") or "").strip()
        current_owner = self._current_turn_owner_id(game=game)
        if expected_owner and current_owner and expected_owner != current_owner:
            return False, ""
        try:
            expected_turn = int(sr.get(self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_TURN_KEY, 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0
        current_turn = self._current_turn(game=game)
        if expected_turn and current_turn and expected_turn != current_turn:
            return False, ""
        source = str(
            sr.get(self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_SOURCE_KEY, "")
            or self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_SOURCE
        ).strip() or self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_SOURCE
        return True, source

    def set_soulforged_warpack_tempting_addendum_state(
        self,
        unit,
        *,
        active: bool,
        phase_name: str = "",
        source: str = "",
        game=None,
        player=None,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        updated = dict(sr)
        if not bool(active):
            updated.pop(self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_ACTIVE_KEY, None)
            updated.pop(self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_EXPIRES_PHASE_KEY, None)
            updated.pop(self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_TURN_KEY, None)
            updated.pop(self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_OWNER_KEY, None)
            updated.pop(self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_SOURCE_KEY, None)
            root.special_rules = updated
            return
        updated[self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_ACTIVE_KEY] = True
        updated[self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_EXPIRES_PHASE_KEY] = (
            str(phase_name or "").strip().upper() or self._current_phase_name(game=game)
        )
        updated[self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_TURN_KEY] = int(self._current_turn(game=game) or 0)
        updated[self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_OWNER_KEY] = str(
            self._current_turn_owner_id(game=game, player=player) or ""
        ).strip()
        updated[self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_SOURCE_KEY] = (
            str(source or self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_SOURCE).strip()
            or self._SOULFORGED_WARPACK_TEMPTING_ADDENDUM_SOURCE
        )
        root.special_rules = updated

    def soulforged_warpack_tempting_addendum_reroll_hit_applies(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        _ = weapon_profile
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return False, ""
        return self._soulforged_warpack_tempting_addendum_state(root, game=game)

    def _model_within_range_of_unit_allow_destroyed_target(
        self,
        source_model,
        target_unit,
        *,
        range_in: float,
    ) -> bool:
        if source_model is None or target_unit is None:
            return False
        if not self._model_alive(source_model):
            return False
        try:
            radius = float(range_in)
        except (TypeError, ValueError):
            return False
        if radius < 0:
            return False
        get_models = getattr(target_unit, "get_attached_unit_models", None)
        target_models = list(get_models() or []) if callable(get_models) else list(getattr(target_unit, "models", []) or [])
        if not target_models:
            return False
        from ..utility.aura_utils import distance_between_models_bases_3d

        for target_model in target_models:
            if target_model is None:
                continue
            try:
                distance = float(distance_between_models_bases_3d(source_model, target_model))
            except (TypeError, ValueError, AttributeError):
                continue
            if distance <= radius + 1e-6:
                return True
        return False

    def soulforged_soul_harvester_on_enemy_unit_destroyed(self, destroyed_unit, *, game=None) -> list[dict]:
        if not self.is_soulforged_warpack() or self.army is None:
            return []
        destroyed_root = self._unit_root(destroyed_unit)
        if destroyed_root is None:
            return []
        destroyed_army = getattr(destroyed_root, "get_parent_army", None)
        destroyed_owner = destroyed_army() if callable(destroyed_army) else None
        if destroyed_owner is None or destroyed_owner is self.army:
            return []
        owner = getattr(self.army, "player", None)
        gain_cp = getattr(owner, "gain_command_points", None) if owner is not None else None
        if not callable(gain_cp):
            return []
        results: list[dict] = []
        for source_root, _source_member, source_sr, source_bearer in self._soulforged_sources_by_flag(
            flag_key="enhancement_soul_harvester"
        ):
            if source_sr is None or source_bearer is None:
                continue
            if bool(source_sr.get("enhancement_soul_harvester_requires_bearer_on_battlefield", True)):
                bearer_unit = self._unit_root(getattr(source_bearer, "parent_unit", None))
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue
            try:
                range_in = float(source_sr.get("enhancement_soul_harvester_range", 12.0) or 12.0)
            except (TypeError, ValueError):
                range_in = 12.0
            if not self._model_within_range_of_unit_allow_destroyed_target(
                source_bearer,
                destroyed_root,
                range_in=range_in,
            ):
                continue
            try:
                success_on = int(source_sr.get("enhancement_soul_harvester_success_on", 5) or 5)
            except (TypeError, ValueError):
                success_on = 5
            success_on = int(min(6, max(2, success_on)))
            try:
                cp_gain = int(source_sr.get("enhancement_soul_harvester_cp_gain", 1) or 1)
            except (TypeError, ValueError):
                cp_gain = 1
            cp_gain = int(max(1, cp_gain))
            source = str(
                source_sr.get("enhancement_soul_harvester_source", "")
                or self._SOULFORGED_WARPACK_SOUL_HARVESTER_SOURCE
            ).strip() or self._SOULFORGED_WARPACK_SOUL_HARVESTER_SOURCE
            roll = int(get_roll("D6"))
            gained = 0
            if roll >= success_on:
                gained = int(gain_cp(cp_gain, reason=source) or 0)
            results.append(
                {
                    "triggered": True,
                    "source": source,
                    "roll": int(roll),
                    "success_on": int(success_on),
                    "cp_gain": int(cp_gain),
                    "gained": int(gained),
                    "destroyed_unit_id": str(get_entity_id(destroyed_root) or ""),
                    "source_unit_id": str(get_entity_id(source_root) or ""),
                    "source_model_id": str(get_entity_id(source_bearer) or ""),
                }
            )
        return results

    def twisted_doctrine_can_trigger(
        self,
        unit,
        *,
        action: str,
        game=None,
        player=None,
        set_up_as_reinforcements: bool = False,
    ) -> bool:
        if not self.is_renegade_warband():
            return False
        action_key = str(action or "").strip().lower()
        if action_key not in self._TWISTED_DOCTRINE_ALLOWED_ACTIONS:
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_on_battlefield(root):
            return False
        if not self._unit_is_heretic_astartes(root):
            return False
        if self._unit_is_battle_shocked(root):
            return False
        if action_key == "set_up" and bool(set_up_as_reinforcements):
            arrived = getattr(root, "arrived_from_reserves_this_turn", None)
            if arrived is not None and not bool(arrived):
                return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        phase_name = self._current_phase_name(game=game)
        if phase_name and phase_name != "MOVEMENT_PHASE":
            return False
        current_owner = str(self._current_turn_owner_id(game=game, player=owner) or "")
        if current_owner and current_owner != str(getattr(owner, "id", "") or ""):
            return False
        return True

    def _pending_twisted_doctrine_choice_request(
        self,
        game,
        *,
        unit_id: str,
        instance_key: str,
    ) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != self._RENEGADE_WARBAND_TWISTED_DOCTRINE_ABILITY:
                continue
            if str(ctx.get("unit_id", "") or "") != str(unit_id or ""):
                continue
            if str(ctx.get("ability_instance", "") or "").strip().lower() != str(instance_key or "").strip().lower():
                continue
            return True
        return False

    def queue_twisted_doctrine_choice_request(
        self,
        unit,
        *,
        action: str,
        game=None,
        player=None,
        set_up_as_reinforcements: bool = False,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None or not bool(getattr(resolved_game, "is_authoritative", True)):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        action_key = str(action or "").strip().lower()
        if not self.twisted_doctrine_can_trigger(
            root,
            action=action_key,
            game=resolved_game,
            player=owner,
            set_up_as_reinforcements=set_up_as_reinforcements,
        ):
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return
        turn = int(self._current_turn(game=resolved_game) or 0)
        phase_name = str(self._current_phase_name(game=resolved_game) or "")
        owner_id = str(self._current_turn_owner_id(game=resolved_game, player=owner) or "")
        instance_key = (
            f"{unit_id}:{turn}:{phase_name}:{owner_id}:{action_key}:"
            f"{int(bool(set_up_as_reinforcements))}:twisted_doctrine"
        )
        if self._pending_twisted_doctrine_choice_request(
            resolved_game,
            unit_id=unit_id,
            instance_key=instance_key,
        ):
            return

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            (
                f"Twisted Doctrine: choose an effect for {getattr(root, 'name', 'Unit')} "
                "or select None."
            ),
            player_id=getattr(owner, "id", None),
            options=[
                DecisionOption.create(
                    "Shoot and charge after Falling Back",
                    payload={
                        "choice_key": self._RENEGADE_WARBAND_TWISTED_DOCTRINE_FALL_BACK_CHOICE,
                        "unit_id": unit_id,
                        "trigger_action": action_key,
                        "set_up_as_reinforcements": bool(set_up_as_reinforcements),
                    },
                ),
                DecisionOption.create(
                    "Charge after Advancing",
                    payload={
                        "choice_key": self._RENEGADE_WARBAND_TWISTED_DOCTRINE_ADVANCE_CHOICE,
                        "unit_id": unit_id,
                        "trigger_action": action_key,
                        "set_up_as_reinforcements": bool(set_up_as_reinforcements),
                    },
                ),
                DecisionOption.create(
                    "None",
                    payload={
                        "action": "skip",
                        "skip": True,
                        "unit_id": unit_id,
                        "trigger_action": action_key,
                        "set_up_as_reinforcements": bool(set_up_as_reinforcements),
                    },
                ),
            ],
            context={
                "ability": self._RENEGADE_WARBAND_TWISTED_DOCTRINE_ABILITY,
                "ability_name": self._RENEGADE_WARBAND_TWISTED_DOCTRINE_SOURCE,
                "phase": "Movement phase",
                "unit_id": unit_id,
                "trigger_action": action_key,
                "set_up_as_reinforcements": bool(set_up_as_reinforcements),
                "turn": int(turn),
                "turn_owner_id": owner_id,
                "ability_instance": instance_key,
                "allowed_choice_keys": [
                    self._RENEGADE_WARBAND_TWISTED_DOCTRINE_FALL_BACK_CHOICE,
                    self._RENEGADE_WARBAND_TWISTED_DOCTRINE_ADVANCE_CHOICE,
                ],
                "optional": True,
            },
        )
        if hasattr(resolved_game, "request_decision"):
            resolved_game.request_decision(request)

    def _twisted_doctrine_active_state(self, unit, *, game=None) -> tuple[bool, bool]:
        if not self.is_renegade_warband():
            return False, False
        root = self._unit_root(unit)
        if root is None:
            return False, False
        if not self._unit_in_army(root):
            return False, False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False, False
        if not bool(sr.get("renegade_warband_twisted_doctrine_active", False)):
            return False, False
        expected_owner = str(sr.get("renegade_warband_twisted_doctrine_turn_owner", "") or "").strip()
        expected_turn = int(sr.get("renegade_warband_twisted_doctrine_turn", 0) or 0)
        current_owner = str(self._current_turn_owner_id(game=game) or "")
        current_turn = int(self._current_turn(game=game) or 0)
        if expected_owner and current_owner and expected_owner != current_owner:
            return False, False
        if expected_turn and current_turn and expected_turn != current_turn:
            return False, False
        fall_back_mode = bool(sr.get("renegade_warband_twisted_doctrine_fall_back_mode", False))
        advance_mode = bool(sr.get("renegade_warband_twisted_doctrine_advance_mode", False))
        return fall_back_mode, advance_mode

    def _renegade_warband_default_to_doctrine_active_state(self, unit, *, game=None) -> bool:
        if not self.is_renegade_warband():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("renegade_warband_default_to_doctrine_active", False)):
            return False
        expected_owner = str(sr.get("renegade_warband_default_to_doctrine_turn_owner", "") or "").strip()
        expected_turn = int(sr.get("renegade_warband_default_to_doctrine_turn", 0) or 0)
        current_owner = str(self._current_turn_owner_id(game=game) or "")
        current_turn = int(self._current_turn(game=game) or 0)
        if expected_owner and current_owner and expected_owner != current_owner:
            return False
        if expected_turn and current_turn and expected_turn != current_turn:
            return False
        return True

    def activate_twisted_doctrine(
        self,
        unit,
        *,
        choice_key: str,
        action: str,
        game=None,
        player=None,
        set_up_as_reinforcements: bool = False,
    ) -> dict:
        root = self._unit_root(unit)
        if root is None:
            return {"ok": False, "reason": "Unit not found."}
        if not self.twisted_doctrine_can_trigger(
            root,
            action=action,
            game=game,
            player=player,
            set_up_as_reinforcements=set_up_as_reinforcements,
        ):
            return {"ok": False, "reason": "Twisted Doctrine cannot trigger for this unit/action."}
        key = str(choice_key or "").strip().upper()
        if key not in {
            self._RENEGADE_WARBAND_TWISTED_DOCTRINE_FALL_BACK_CHOICE,
            self._RENEGADE_WARBAND_TWISTED_DOCTRINE_ADVANCE_CHOICE,
        }:
            return {"ok": False, "reason": "Twisted Doctrine choice is invalid."}

        take_test = getattr(root, "take_battle_shock_test", None)
        if callable(take_test):
            take_test(int(self._current_turn(game=game) or 1))

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        updated = dict(sr)
        updated["renegade_warband_twisted_doctrine_active"] = True
        updated["renegade_warband_twisted_doctrine_turn"] = int(self._current_turn(game=game) or 0)
        updated["renegade_warband_twisted_doctrine_turn_owner"] = str(
            self._current_turn_owner_id(game=game, player=player) or ""
        )
        updated["renegade_warband_default_to_doctrine_active"] = True
        updated["renegade_warband_default_to_doctrine_turn"] = int(self._current_turn(game=game) or 0)
        updated["renegade_warband_default_to_doctrine_turn_owner"] = str(
            self._current_turn_owner_id(game=game, player=player) or ""
        )
        updated["renegade_warband_twisted_doctrine_source"] = self._RENEGADE_WARBAND_TWISTED_DOCTRINE_SOURCE
        updated["renegade_warband_twisted_doctrine_action"] = str(action or "").strip().lower()
        if key == self._RENEGADE_WARBAND_TWISTED_DOCTRINE_FALL_BACK_CHOICE:
            updated["renegade_warband_twisted_doctrine_fall_back_mode"] = True
        if key == self._RENEGADE_WARBAND_TWISTED_DOCTRINE_ADVANCE_CHOICE:
            updated["renegade_warband_twisted_doctrine_advance_mode"] = True
        root.special_rules = updated

        label = "Shoot and charge after Falling Back"
        if key == self._RENEGADE_WARBAND_TWISTED_DOCTRINE_ADVANCE_CHOICE:
            label = "Charge after Advancing"
        return {
            "ok": True,
            "unit_id": str(get_entity_id(root) or ""),
            "choice_key": key,
            "label": label,
            "source": self._RENEGADE_WARBAND_TWISTED_DOCTRINE_SOURCE,
            "is_battle_shocked": bool(self._unit_is_battle_shocked(root)),
        }

    def twisted_doctrine_can_shoot_after_fall_back(self, unit, profile=None, *, game=None) -> bool:
        fall_back_mode, _advance_mode = self._twisted_doctrine_active_state(unit, game=game)
        if not fall_back_mode:
            return False
        parent = getattr(profile, "parent_wargear", None) if profile is not None else None
        is_ranged = getattr(parent, "is_ranged", None) if parent is not None else None
        if callable(is_ranged):
            return bool(is_ranged())
        return True

    def twisted_doctrine_can_charge_after_fall_back(self, unit, *, game=None) -> bool:
        fall_back_mode, _advance_mode = self._twisted_doctrine_active_state(unit, game=game)
        return bool(fall_back_mode)

    def twisted_doctrine_can_charge_after_advance(self, unit, *, game=None) -> bool:
        _fall_back_mode, advance_mode = self._twisted_doctrine_active_state(unit, game=game)
        return bool(advance_mode)

    @staticmethod
    def _renegade_warband_effect_source(sr: dict, *, prefix: str, default: str) -> str:
        return str(sr.get(f"{prefix}_source", "") or default).strip() or default

    def _renegade_warband_effect_state(
        self,
        unit,
        *,
        prefix: str,
        game=None,
        require_phase_match: bool = True,
    ):
        if not self.is_renegade_warband():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None, None
        if not bool(sr.get(f"{prefix}_active", False)):
            return None, None

        expected_phase = str(sr.get(f"{prefix}_phase", "") or "").strip().upper()
        expected_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if require_phase_match and expected_phase and current_phase and expected_phase != current_phase:
            return None, None
        if expected_owner and current_owner and expected_owner != current_owner:
            return None, None
        if expected_turn and current_turn and expected_turn != current_turn:
            return None, None
        return root, sr

    def _set_renegade_warband_effect_state(
        self,
        unit,
        *,
        prefix: str,
        source: str,
        player=None,
        game=None,
        extra_state: Optional[dict] = None,
        track_phase: bool = True,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        if track_phase:
            sr[f"{prefix}_phase"] = self._current_phase_name(game=game)
        else:
            sr.pop(f"{prefix}_phase", None)
        sr[f"{prefix}_turn"] = self._current_turn(game=game)
        sr[f"{prefix}_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr[f"{prefix}_source"] = str(source or "").strip() or str(prefix).replace("_", " ").title()
        for key, value in dict(extra_state or {}).items():
            sr[str(key)] = value
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

    def renegade_warband_corrupted_munitions_ranged_ap_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged"):
            return 0, ""
        root, sr = self._renegade_warband_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._RENEGADE_WARBAND_CORRUPTED_MUNITIONS_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return 0, ""
        try:
            bonus = int(sr.get(f"{self._RENEGADE_WARBAND_CORRUPTED_MUNITIONS_PREFIX}_ap_bonus", 1) or 0)
        except (TypeError, ValueError):
            bonus = 1
        if bonus <= 0:
            return 0, ""
        return int(bonus), self._renegade_warband_effect_source(
            sr,
            prefix=self._RENEGADE_WARBAND_CORRUPTED_MUNITIONS_PREFIX,
            default=self._RENEGADE_WARBAND_CORRUPTED_MUNITIONS_SOURCE,
        )

    def renegade_warband_vengeful_destruction_wound_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        _ = weapon_profile
        if attacker_model is None or target_unit is None or not self._model_in_army(attacker_model):
            return 0, ""
        root, sr = self._renegade_warband_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._RENEGADE_WARBAND_VENGEFUL_DESTRUCTION_PREFIX,
            game=game,
        )
        if root is None:
            return 0, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return 0, ""
        vendetta_target_id = str(self.renegade_warband_vendetta_target_unit_id or "").strip()
        if not vendetta_target_id:
            return 0, ""
        if str(get_entity_id(target_root) or "").strip() != vendetta_target_id:
            return 0, ""
        try:
            bonus = int(sr.get(f"{self._RENEGADE_WARBAND_VENGEFUL_DESTRUCTION_PREFIX}_wound_bonus", 1) or 0)
        except (TypeError, ValueError):
            bonus = 1
        if bonus <= 0:
            return 0, ""
        return int(bonus), self._renegade_warband_effect_source(
            sr,
            prefix=self._RENEGADE_WARBAND_VENGEFUL_DESTRUCTION_PREFIX,
            default=self._RENEGADE_WARBAND_VENGEFUL_DESTRUCTION_SOURCE,
        )

    @staticmethod
    def _normalize_name(value: str) -> str:
        return " ".join(str(value or "").strip().lower().split())

    @classmethod
    def _is_fabius_bile_name(cls, value: str) -> bool:
        return cls._normalize_name(value) == "fabius bile"

    def _warlord_root(self):
        if self.army is None:
            return None
        warlord = getattr(self.army, "warlord", None)
        if warlord is None:
            for unit in list(getattr(self.army, "units", []) or []):
                if bool(getattr(unit, "is_warlord", False)):
                    warlord = unit
                    break
        return self._unit_root(warlord)

    def has_fabius_bile_warlord(self) -> bool:
        warlord = self._warlord_root()
        if warlord is None:
            return False
        if self._is_fabius_bile_name(getattr(warlord, "name", "")):
            return True
        members_fn = getattr(warlord, "get_attached_unit_members", None)
        if callable(members_fn):
            for member in list(members_fn() or []):
                if bool(getattr(member, "is_warlord", False)) and self._is_fabius_bile_name(getattr(member, "name", "")):
                    return True
        return False

    def _unit_is_creations_eligible(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_has_keyword(root, "HERETIC ASTARTES"):
            return False
        if not self._unit_has_keyword(root, "INFANTRY"):
            return False
        if self._unit_has_keyword(root, "DAMNED"):
            return False
        return True

    def _model_is_creations_eligible(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        return self._unit_is_creations_eligible(unit)

    @staticmethod
    def experimental_augmentations_catalog() -> tuple[ExperimentalAugmentation, ...]:
        return EXPERIMENTAL_AUGMENTATIONS

    @staticmethod
    def experimental_augmentation_name(key: str) -> str:
        aug = EXPERIMENTAL_AUGMENTATION_BY_KEY.get(str(key or "").strip().upper())
        if aug is None:
            return str(key or "").strip()
        return aug.name

    def describe_experimental_augmentation_keys(self, keys: Iterable[str]) -> list[str]:
        out: list[str] = []
        for key in list(keys or []):
            name = self.experimental_augmentation_name(str(key or "").strip().upper())
            if name and name not in out:
                out.append(name)
        return out

    def can_select_experimental_augmentations(self, *, game=None, battle_round: Optional[int] = None) -> bool:
        if not self.is_creations_of_bile():
            return False
        if self.experimental_augmentations_selected:
            return False
        if self.experimental_augmentations_pending_rolls:
            return False
        round_value = battle_round
        if round_value is None and game is not None:
            try:
                round_value = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                round_value = 0
        if round_value is not None and int(round_value or 0) > 1:
            return False
        return True

    @staticmethod
    def _dedupe_augmentation_keys(keys: Iterable[str]) -> list[str]:
        unique: list[str] = []
        for key in list(keys or []):
            norm = str(key or "").strip().upper()
            if norm not in EXPERIMENTAL_AUGMENTATION_BY_KEY:
                continue
            if norm in unique:
                continue
            unique.append(norm)
        return unique

    @staticmethod
    def _augmentation_keys_from_rolls(rolls: Iterable[int]) -> list[str]:
        keys: list[str] = []
        for roll in list(rolls or []):
            try:
                value = int(roll or 0)
            except (TypeError, ValueError):
                continue
            aug = EXPERIMENTAL_AUGMENTATION_BY_ROLL.get(value)
            if aug is None:
                continue
            keys.append(aug.key)
        return ChaosSpaceMarinesDetachmentManager._dedupe_augmentation_keys(keys)

    def _clear_pending_experimental_augmentation_rolls(self) -> None:
        self.experimental_augmentations_pending_rolls = []
        self.experimental_augmentations_pending_round = None

    def _finalize_experimental_augmentations(
        self,
        *,
        keys: Iterable[str],
        battle_round: Optional[int],
        mode: str,
        rolls: Optional[Iterable[int]] = None,
    ) -> None:
        final_keys = self._dedupe_augmentation_keys(keys)
        self.experimental_augmentations_active_keys = set(final_keys)
        self.experimental_augmentations_selected = True
        self.experimental_augmentations_selection_mode = str(mode or "").strip().lower() or "manual"
        if battle_round is not None:
            try:
                self.experimental_augmentations_selected_round = int(battle_round)
            except (TypeError, ValueError):
                self.experimental_augmentations_selected_round = None
        else:
            self.experimental_augmentations_selected_round = None
        self.experimental_augmentations_rolls = [int(v) for v in list(rolls or [])]
        self._clear_pending_experimental_augmentation_rolls()

    def select_experimental_augmentation(self, choice_key: str, *, battle_round: Optional[int] = None) -> bool:
        if not self.can_select_experimental_augmentations(battle_round=battle_round):
            return False
        key = str(choice_key or "").strip().upper()
        if key not in EXPERIMENTAL_AUGMENTATION_BY_KEY:
            return False
        self._finalize_experimental_augmentations(
            keys=[key],
            battle_round=battle_round,
            mode="manual",
            rolls=[],
        )
        return True

    def roll_experimental_augmentations_initial(self, *, battle_round: Optional[int] = None, game=None) -> dict:
        if not self.can_select_experimental_augmentations(game=game, battle_round=battle_round):
            return {"ok": False, "reason": "Experimental Augmentations cannot be selected right now."}
        rolls = [int(get_roll("D6") or 0), int(get_roll("D6") or 0)]
        selected_keys = self._augmentation_keys_from_rolls(rolls)
        fabius_warlord = bool(self.has_fabius_bile_warlord())
        if not fabius_warlord:
            self._finalize_experimental_augmentations(
                keys=selected_keys,
                battle_round=battle_round,
                mode="random",
                rolls=rolls,
            )
            return {
                "ok": True,
                "rolls": list(rolls),
                "selected_keys": list(selected_keys),
                "requires_reroll_choice": False,
                "finalized": True,
            }
        self.experimental_augmentations_pending_rolls = list(rolls)
        if battle_round is not None:
            try:
                self.experimental_augmentations_pending_round = int(battle_round)
            except (TypeError, ValueError):
                self.experimental_augmentations_pending_round = None
        else:
            self.experimental_augmentations_pending_round = None
        return {
            "ok": True,
            "rolls": list(rolls),
            "selected_keys": list(selected_keys),
            "requires_reroll_choice": True,
            "finalized": False,
        }

    def has_pending_experimental_augmentations_rolls(self) -> bool:
        return bool(self.experimental_augmentations_pending_rolls) and not self.experimental_augmentations_selected

    def resolve_experimental_augmentations_reroll(self, mode: str, *, battle_round: Optional[int] = None) -> dict:
        if not self.has_pending_experimental_augmentations_rolls():
            return {"ok": False, "reason": "No pending Experimental Augmentations rolls."}
        reroll_mode = str(mode or "").strip().lower()
        if reroll_mode not in self._EXPERIMENTAL_AUGMENTATION_REROLL_MODES:
            return {"ok": False, "reason": "Invalid Experimental Augmentations reroll mode."}

        original_rolls = list(self.experimental_augmentations_pending_rolls)
        updated_rolls = list(original_rolls)
        if reroll_mode in {"reroll_first", "reroll_both"}:
            updated_rolls[0] = int(get_roll("D6") or 0)
        if reroll_mode in {"reroll_second", "reroll_both"}:
            updated_rolls[1] = int(get_roll("D6") or 0)
        selected_keys = self._augmentation_keys_from_rolls(updated_rolls)

        selected_round = battle_round
        if selected_round is None:
            selected_round = self.experimental_augmentations_pending_round
        self._finalize_experimental_augmentations(
            keys=selected_keys,
            battle_round=selected_round,
            mode="random",
            rolls=updated_rolls,
        )
        return {
            "ok": True,
            "reroll_mode": reroll_mode,
            "original_rolls": original_rolls,
            "rolls": updated_rolls,
            "selected_keys": list(selected_keys),
            "finalized": True,
        }

    def get_active_experimental_augmentation_keys_for_model(self, model, *, game=None) -> set[str]:
        if not self.is_creations_of_bile():
            return set()
        if not self._model_is_creations_eligible(model):
            return set()
        active_keys = set(self.experimental_augmentations_active_keys) if self.experimental_augmentations_selected else set()
        _root, sr = self._creations_of_bile_delayed_mutations_state(getattr(model, "parent_unit", None), game=game)
        if isinstance(sr, dict):
            choice_key = str(sr.get(f"{self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX}_choice_key", "") or "").strip().upper()
            if choice_key in EXPERIMENTAL_AUGMENTATION_BY_KEY:
                active_keys.add(choice_key)
        return active_keys

    def experimental_augmentations_movement_bonus(self, model=None, unit=None, *, game=None) -> tuple[int, str]:
        target_model = model
        if target_model is None and unit is not None:
            models = list(getattr(unit, "models", []) or [])
            if models:
                target_model = models[0]
        if target_model is None:
            return 0, ""
        keys = self.get_active_experimental_augmentation_keys_for_model(target_model)
        if HYPERADRENAL_INFUSION.key not in keys:
            return 0, ""
        return 2, HYPERADRENAL_INFUSION.name

    def experimental_augmentations_toughness_bonus(self, model=None, unit=None, *, game=None) -> tuple[int, str]:
        target_model = model
        if target_model is None and unit is not None:
            models = list(getattr(unit, "models", []) or [])
            if models:
                target_model = models[0]
        if target_model is None:
            return 0, ""
        keys = self.get_active_experimental_augmentation_keys_for_model(target_model)
        if SUPRACUTANEOUS_CHITINATION.key not in keys:
            return 0, ""
        return 1, SUPRACUTANEOUS_CHITINATION.name

    def experimental_augmentations_melee_attacks_bonus(self, model, weapon_profile=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee = getattr(parent, "is_melee", None) if parent is not None else None
            if not callable(is_melee) or not bool(is_melee()):
                return 0, ""
        keys = self.get_active_experimental_augmentation_keys_for_model(model)
        if CHOLINERGIC_ACCELERANTS.key not in keys:
            return 0, ""
        return 1, CHOLINERGIC_ACCELERANTS.name

    def experimental_augmentations_melee_skill_bonus(self, model, weapon_profile=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee = getattr(parent, "is_melee", None) if parent is not None else None
            if not callable(is_melee) or not bool(is_melee()):
                return 0, ""
        keys = self.get_active_experimental_augmentation_keys_for_model(model)
        if PARANEURAL_REACTIONS.key not in keys:
            return 0, ""
        return 1, PARANEURAL_REACTIONS.name

    def experimental_augmentations_ranged_skill_bonus(self, model, weapon_profile=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_ranged = getattr(parent, "is_ranged", None) if parent is not None else None
            if not callable(is_ranged) or not bool(is_ranged()):
                return 0, ""
        keys = self.get_active_experimental_augmentation_keys_for_model(model)
        if OPHTHALMIC_ENHANCEMENT.key not in keys:
            return 0, ""
        return 1, OPHTHALMIC_ENHANCEMENT.name

    def experimental_augmentations_melee_strength_bonus(self, model, weapon_profile=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee = getattr(parent, "is_melee", None) if parent is not None else None
            if not callable(is_melee) or not bool(is_melee()):
                return 0, ""
        keys = self.get_active_experimental_augmentation_keys_for_model(model)
        if MACROTENSILE_SINEWS.key not in keys:
            return 0, ""
        return 1, MACROTENSILE_SINEWS.name

    def creations_of_bile_masters_are_watching_fight_on_death_rule(self, unit, *, model=None, game=None) -> Optional[dict]:
        root, sr = self._creations_of_bile_phase_effect_state(
            unit,
            prefix=self._CREATIONS_OF_BILE_MASTERS_ARE_WATCHING_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return None
        threshold = 5 if self._unit_is_damned(root) else 4
        source = str(
            sr.get(f"{self._CREATIONS_OF_BILE_MASTERS_ARE_WATCHING_PREFIX}_source", "")
            or self._CREATIONS_OF_BILE_MASTERS_ARE_WATCHING_SOURCE
        ).strip() or self._CREATIONS_OF_BILE_MASTERS_ARE_WATCHING_SOURCE
        return {"threshold": int(threshold), "source": source}

    def creations_of_bile_specimens_for_the_spider_reroll_wound_applies(
        self,
        attacker_model,
        *,
        target_unit=None,
        attack_type: str = "melee",
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        attack_key = str(attack_type or "").strip().lower()
        if attack_key not in {"any", "melee"}:
            return False, ""
        if target_unit is None or not self._unit_has_keyword(target_unit, "CHARACTER"):
            return False, ""
        root, sr = self._creations_of_bile_phase_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        source = str(
            sr.get(f"{self._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX}_source", "")
            or self._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_SOURCE
        ).strip() or self._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_SOURCE
        return True, source

    def creations_of_bile_specimens_for_the_spider_post_fight_resolution(self, unit, *, game=None) -> Optional[dict]:
        root, sr = self._creations_of_bile_phase_effect_state(
            unit,
            prefix=self._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX,
            game=game,
        )
        if root is None or not isinstance(sr, dict):
            return None
        if bool(sr.get(f"{self._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX}_resolved", False)):
            return None

        source = str(
            sr.get(f"{self._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX}_source", "")
            or self._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_SOURCE
        ).strip() or self._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_SOURCE

        baseline_character_ids = {
            str(value or "").strip()
            for value in list(
                sr.get(f"{self._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX}_enemy_character_model_ids", []) or []
            )
            if str(value or "").strip()
        }
        baseline_warlord_ids = {
            str(value or "").strip()
            for value in list(
                sr.get(f"{self._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX}_enemy_warlord_model_ids", []) or []
            )
            if str(value or "").strip()
        }
        current_character_ids = set(self._collect_destroyed_enemy_character_model_ids(root, game=game))
        current_warlord_ids = set(self._collect_destroyed_enemy_character_model_ids(root, warlord_only=True, game=game))
        new_character_ids = sorted(current_character_ids - baseline_character_ids)
        new_warlord_ids = sorted(current_warlord_ids - baseline_warlord_ids)
        candidates = self._enemy_units_within_range_of_unit(root, range_in=6.0, game=game)

        sr[f"{self._CREATIONS_OF_BILE_SPECIMENS_FOR_THE_SPIDER_PREFIX}_resolved"] = True
        root.special_rules = sr

        if not new_character_ids:
            return None
        return {
            "source": source,
            "warlord_destroyed": bool(new_warlord_ids),
            "candidate_units": list(candidates),
        }

    def creations_of_bile_prime_test_subject_melee_reroll_hit_applies(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        _ = game
        if not self.is_creations_of_bile():
            return False, ""
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee = getattr(parent, "is_melee", None) if parent is not None else None
            if not callable(is_melee) or not bool(is_melee()):
                return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(attacker_unit)
        if root is None or not self._unit_in_army(root):
            return False, ""

        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]

        attacker_entity_id = str(get_entity_id(attacker_model) or "")
        attacker_local_id = str(getattr(attacker_model, "id", getattr(attacker_model, "_id", "")) or "")
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_prime_test_subject", False)):
                continue
            bearer = self._find_enhancement_bearer_on_member(member, sr)
            if not self._model_alive(bearer):
                continue
            bearer_entity_id = str(get_entity_id(bearer) or "")
            bearer_local_id = str(getattr(bearer, "id", getattr(bearer, "_id", "")) or "")
            if attacker_entity_id and bearer_entity_id and attacker_entity_id == bearer_entity_id:
                source = str(sr.get("enhancement_prime_test_subject_source", "") or "Prime Test Subject").strip()
                return True, (source or "Prime Test Subject")
            if attacker_local_id and bearer_local_id and attacker_local_id == bearer_local_id:
                source = str(sr.get("enhancement_prime_test_subject_source", "") or "Prime Test Subject").strip()
                return True, (source or "Prime Test Subject")
        return False, ""

    def _resolve_game(self, *, game=None):
        if game is not None:
            return game
        if self.army is None:
            return None
        player = getattr(self.army, "player", None)
        if player is None:
            return None
        return getattr(player, "game", None)

    def _current_phase_name(self, *, game=None) -> str:
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return ""
        return str(getattr(getattr(resolved_game, "phase", None), "name", "") or "").strip().upper()

    def _current_turn(self, *, game=None) -> int:
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return 0
        try:
            return int(getattr(resolved_game, "turn", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _current_turn_owner_id(self, *, game=None, player=None) -> str:
        resolved_game = self._resolve_game(game=game)
        if resolved_game is not None:
            get_current_player = getattr(resolved_game, "get_current_player", None)
            if callable(get_current_player):
                current_player = get_current_player()
                owner_id = str(getattr(current_player, "id", "") or "").strip()
                if owner_id:
                    return owner_id
        if player is not None:
            owner_id = str(getattr(player, "id", "") or "").strip()
            if owner_id:
                return owner_id
        army_player = getattr(self.army, "player", None) if self.army is not None else None
        return str(getattr(army_player, "id", "") or "").strip()

    @staticmethod
    def _player_index_for_id(resolved_game, player_id: str) -> Optional[int]:
        if resolved_game is None:
            return None
        target_id = str(player_id or "").strip()
        if not target_id:
            return None
        for index, player in enumerate(list(getattr(resolved_game, "players", []) or [])):
            if str(getattr(player, "id", "") or "").strip() == target_id:
                return int(index)
        return None

    @classmethod
    def _remove_special_rule_prefix(cls, root, prefix: str) -> bool:
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        remove_keys = [key for key in list(sr.keys()) if str(key).startswith(str(prefix))]
        if not remove_keys:
            return False
        for key in remove_keys:
            sr.pop(key, None)
        root.special_rules = sr
        cls._clear_unit_ability_cache(root)
        return True

    def _creations_of_bile_phase_effect_state(self, unit, *, prefix: str, game=None):
        if not self.is_creations_of_bile():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None, None
        if not bool(sr.get(f"{prefix}_active", False)):
            return None, None

        expected_phase = str(sr.get(f"{prefix}_phase", "") or "").strip().upper()
        expected_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if expected_phase and current_phase and expected_phase != current_phase:
            return None, None
        if expected_owner and current_owner and expected_owner != current_owner:
            return None, None
        if expected_turn and current_turn and expected_turn != current_turn:
            return None, None
        return root, sr

    def _set_creations_of_bile_phase_effect_state(
        self,
        unit,
        *,
        prefix: str,
        source: str,
        player=None,
        game=None,
        extra_state: Optional[dict] = None,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        sr[f"{prefix}_phase"] = self._current_phase_name(game=game)
        sr[f"{prefix}_turn"] = self._current_turn(game=game)
        sr[f"{prefix}_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr[f"{prefix}_source"] = str(source or "").strip() or str(prefix).replace("_", " ").title()
        for key, value in dict(extra_state or {}).items():
            sr[str(key)] = value
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

    @staticmethod
    def _character_model_id(model) -> str:
        if model is None:
            return ""
        entity_id = str(get_entity_id(model) or "").strip()
        if entity_id:
            return entity_id
        return str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()

    def _model_is_character_for_creations(self, model) -> bool:
        if model is None:
            return False
        char_attr = getattr(model, "is_character", None)
        if bool(char_attr() if callable(char_attr) else char_attr):
            return True
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any) and bool(has_any("CHARACTER")):
            return True
        has_keyword = getattr(model, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword("CHARACTER")):
            return True
        parent = getattr(model, "parent_unit", None)
        return bool(parent is not None and self._unit_has_keyword(parent, "CHARACTER"))

    def _model_is_warlord_for_creations(self, model) -> bool:
        if model is None:
            return False
        warlord_attr = getattr(model, "is_warlord", None)
        if bool(warlord_attr() if callable(warlord_attr) else warlord_attr):
            return True
        parent = getattr(model, "parent_unit", None)
        if parent is None:
            return False
        if bool(getattr(parent, "is_warlord", False)):
            return True
        army = getattr(parent, "get_parent_army", lambda: None)()
        warlord = getattr(army, "warlord", None) if army is not None else None
        if warlord is None:
            return False
        try:
            warlord_root = warlord.get_attached_unit_root()
        except Exception:
            warlord_root = warlord
        try:
            parent_root = parent.get_attached_unit_root()
        except Exception:
            parent_root = parent
        return parent_root is not None and warlord_root is parent_root

    def _collect_destroyed_enemy_character_model_ids(self, source_unit, *, warlord_only: bool = False, game=None) -> list[str]:
        root = self._unit_root(source_unit)
        if root is None:
            return []
        source_army = getattr(root, "get_parent_army", lambda: None)()
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return []

        out: set[str] = set()
        for player in list(getattr(resolved_game, "players", []) or []):
            army = getattr(player, "get_army", lambda: None)()
            if army is None or army is source_army:
                continue
            for unit in list(getattr(army, "units", []) or []):
                unit_root = self._unit_root(unit)
                if unit_root is None:
                    continue
                members_fn = getattr(unit_root, "get_attached_unit_members", None)
                members = list(members_fn() or []) if callable(members_fn) else [unit_root]
                if not members:
                    members = [unit_root]
                for member in list(members or []):
                    for model in list(getattr(member, "models_lost", []) or []):
                        if not self._model_is_character_for_creations(model):
                            continue
                        if warlord_only and not self._model_is_warlord_for_creations(model):
                            continue
                        model_id = self._character_model_id(model)
                        if model_id:
                            out.add(model_id)
        return sorted(out)

    def _enemy_units_within_range_of_unit(self, source_unit, *, range_in: float, game=None) -> list:
        root = self._unit_root(source_unit)
        resolved_game = self._resolve_game(game=game)
        game_map = getattr(resolved_game, "map", None) if resolved_game is not None else None
        if root is None or game_map is None or float(range_in or 0.0) <= 0:
            return []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []

        from ..utility.aura_utils import unit_within_range_of_unit

        candidates: list = []
        seen: set[str] = set()
        for unit in list(get_enemy_units(root) or []):
            enemy_root = self._unit_root(unit)
            if enemy_root is None:
                continue
            unit_id = self._unit_entity_key(enemy_root)
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            if not self._unit_on_battlefield(enemy_root):
                continue
            if not unit_within_range_of_unit(root, enemy_root, float(range_in), use_attached_aggregate=True):
                continue
            candidates.append(enemy_root)
        return sorted(candidates, key=self._unit_entity_key)

    def _creations_of_bile_delayed_mutations_is_expired(self, sr: dict, *, game=None) -> bool:
        if not isinstance(sr, dict):
            return True
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return False
        try:
            activation_round = int(sr.get(f"{self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX}_turn", 0) or 0)
        except (TypeError, ValueError):
            activation_round = 0
        if activation_round <= 0:
            return False
        try:
            current_round = int(getattr(resolved_game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_round = 0
        if current_round <= activation_round:
            return False
        if current_round > activation_round + 1:
            return True

        owner_id = str(sr.get(f"{self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX}_activating_player_id", "") or "").strip()
        if not owner_id:
            return True
        owner_index = self._player_index_for_id(resolved_game, owner_id)
        if owner_index is None:
            current_owner = self._current_turn_owner_id(game=resolved_game)
            return bool(current_owner and current_owner == owner_id and self._current_phase_name(game=resolved_game))
        try:
            raw_current_index = getattr(resolved_game, "current_player_index", None)
            current_index = -1 if raw_current_index is None else int(raw_current_index)
        except (TypeError, ValueError):
            current_index = -1
        if current_index < 0:
            return False
        if current_index < owner_index:
            return False
        if current_index > owner_index:
            return True
        return bool(self._current_phase_name(game=resolved_game))

    def _creations_of_bile_delayed_mutations_state(self, unit, *, game=None):
        if not self.is_creations_of_bile():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(f"{self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX}_active", False)):
            return None, None
        choice_key = str(sr.get(f"{self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX}_choice_key", "") or "").strip().upper()
        if choice_key not in EXPERIMENTAL_AUGMENTATION_BY_KEY:
            self._remove_special_rule_prefix(root, self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX)
            return None, None
        if self._creations_of_bile_delayed_mutations_is_expired(sr, game=game):
            self._remove_special_rule_prefix(root, self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX)
            return None, None
        return root, sr

    def activate_creations_of_bile_delayed_mutations(
        self,
        unit,
        *,
        choice_key: str,
        game=None,
        player=None,
        source: str = "",
    ) -> dict:
        if not self.is_creations_of_bile():
            return {"ok": False, "reason": "Creations of Bile is not active."}
        root = self._unit_root(unit)
        if root is None or not self._unit_is_creations_eligible(root):
            return {"ok": False, "reason": "Target unit is not eligible for Delayed Mutations."}
        key = str(choice_key or "").strip().upper()
        if key not in EXPERIMENTAL_AUGMENTATION_BY_KEY:
            return {"ok": False, "reason": "Invalid augmentation choice."}
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX}_active"] = True
        sr[f"{self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX}_choice_key"] = key
        sr[f"{self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX}_source"] = (
            str(source or self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_SOURCE).strip()
            or self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_SOURCE
        )
        sr[f"{self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX}_turn"] = self._current_turn(game=game)
        sr[f"{self._CREATIONS_OF_BILE_DELAYED_MUTATIONS_PREFIX}_activating_player_id"] = self._current_turn_owner_id(
            game=game,
            player=player,
        )
        root.special_rules = sr
        self._clear_unit_ability_cache(root)
        return {
            "ok": True,
            "unit_id": self._unit_entity_key(root),
            "choice_key": key,
            "choice_name": self.experimental_augmentation_name(key),
        }

    def soulforged_warpack_can_invoke_contract(self, unit, *, game=None) -> bool:
        if not self.is_soulforged_warpack():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_on_battlefield(root):
            return False
        if not self._unit_is_heretic_astartes(root):
            return False
        if not self._unit_is_daemon_vehicle(root):
            return False
        return bool(self._unit_has_dark_pacts(root))

    def soulforged_warpack_dark_pact_test_modifier(
        self,
        unit,
        *,
        invoke_contract: bool,
        game=None,
    ) -> tuple[int, str]:
        if not bool(invoke_contract):
            return 0, ""
        if not self.soulforged_warpack_can_invoke_contract(unit, game=game):
            return 0, ""
        return -1, self._SOULFORGED_WARPACK_CONTRACT_SOURCE

    def set_soulforged_warpack_dark_pact_test_modifier(
        self,
        unit,
        *,
        modifier: int,
        source: str = "",
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        updated = dict(sr)
        if int(modifier or 0):
            updated[self._SOULFORGED_WARPACK_DARK_PACT_TEST_MODIFIER_KEY] = int(modifier)
            updated[self._SOULFORGED_WARPACK_DARK_PACT_TEST_MODIFIER_SOURCE_KEY] = (
                str(source or self._SOULFORGED_WARPACK_CONTRACT_SOURCE).strip()
                or self._SOULFORGED_WARPACK_CONTRACT_SOURCE
            )
        else:
            updated.pop(self._SOULFORGED_WARPACK_DARK_PACT_TEST_MODIFIER_KEY, None)
            updated.pop(self._SOULFORGED_WARPACK_DARK_PACT_TEST_MODIFIER_SOURCE_KEY, None)
        root.special_rules = updated

    def _soulforged_warpack_contract_state(self, unit, *, game=None) -> tuple[bool, str]:
        if not self.is_soulforged_warpack():
            return False, ""
        root = self._unit_root(unit)
        if root is None:
            return False, ""
        if not self._unit_in_army(root):
            return False, ""
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False, ""
        if not bool(sr.get(self._SOULFORGED_WARPACK_CONTRACT_ACTIVE_KEY, False)):
            return False, ""
        expected_phase = str(sr.get(self._SOULFORGED_WARPACK_CONTRACT_EXPIRES_PHASE_KEY, "") or "").strip().upper()
        current_phase = self._current_phase_name(game=game)
        if expected_phase and current_phase and expected_phase != current_phase:
            return False, ""
        expected_owner = str(sr.get(self._SOULFORGED_WARPACK_CONTRACT_OWNER_KEY, "") or "").strip()
        current_owner = self._current_turn_owner_id(game=game)
        if expected_owner and current_owner and expected_owner != current_owner:
            return False, ""
        try:
            expected_turn = int(sr.get(self._SOULFORGED_WARPACK_CONTRACT_TURN_KEY, 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0
        current_turn = self._current_turn(game=game)
        if expected_turn and current_turn and expected_turn != current_turn:
            return False, ""
        source = (
            str(sr.get(self._SOULFORGED_WARPACK_CONTRACT_SOURCE_KEY, "") or self._SOULFORGED_WARPACK_CONTRACT_SOURCE).strip()
            or self._SOULFORGED_WARPACK_CONTRACT_SOURCE
        )
        return True, source

    def set_soulforged_warpack_contract_state(
        self,
        unit,
        *,
        active: bool,
        phase_name: str = "",
        choice: str = "",
        game=None,
        player=None,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        updated = dict(sr)
        if not bool(active):
            updated.pop(self._SOULFORGED_WARPACK_CONTRACT_ACTIVE_KEY, None)
            updated.pop(self._SOULFORGED_WARPACK_CONTRACT_EXPIRES_PHASE_KEY, None)
            updated.pop(self._SOULFORGED_WARPACK_CONTRACT_TURN_KEY, None)
            updated.pop(self._SOULFORGED_WARPACK_CONTRACT_OWNER_KEY, None)
            updated.pop(self._SOULFORGED_WARPACK_CONTRACT_SOURCE_KEY, None)
            updated.pop(self._SOULFORGED_WARPACK_CONTRACT_CHOICE_KEY, None)
            root.special_rules = updated
            return

        updated[self._SOULFORGED_WARPACK_CONTRACT_ACTIVE_KEY] = True
        updated[self._SOULFORGED_WARPACK_CONTRACT_EXPIRES_PHASE_KEY] = (
            str(phase_name or "").strip().upper() or self._current_phase_name(game=game)
        )
        updated[self._SOULFORGED_WARPACK_CONTRACT_TURN_KEY] = int(self._current_turn(game=game) or 0)
        updated[self._SOULFORGED_WARPACK_CONTRACT_OWNER_KEY] = str(
            self._current_turn_owner_id(game=game, player=player) or ""
        ).strip()
        updated[self._SOULFORGED_WARPACK_CONTRACT_SOURCE_KEY] = self._SOULFORGED_WARPACK_CONTRACT_SOURCE
        updated[self._SOULFORGED_WARPACK_CONTRACT_CHOICE_KEY] = str(choice or "").strip().upper()
        root.special_rules = updated

    def soulforged_warpack_contract_ranged_wound_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._model_is_heretic_astartes(attacker_model):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_ranged = getattr(parent, "is_ranged", None) if parent is not None else None
            if not callable(is_ranged) or not bool(is_ranged()):
                return 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        if not self._unit_is_daemon_vehicle(root):
            return 0, ""
        active, source = self._soulforged_warpack_contract_state(root, game=game)
        if not active:
            return 0, ""
        return 1, source

    def soulforged_warpack_contract_melee_attacks_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._model_is_heretic_astartes(attacker_model):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee = getattr(parent, "is_melee", None) if parent is not None else None
            if not callable(is_melee) or not bool(is_melee()):
                return 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        if not self._unit_is_daemon_vehicle(root):
            return 0, ""
        active, source = self._soulforged_warpack_contract_state(root, game=game)
        if not active:
            return 0, ""
        return 2, source

    def _soulforged_warpack_effect_state(
        self,
        unit,
        *,
        prefix: str,
        game=None,
        require_phase_match: bool = True,
    ):
        if not self.is_soulforged_warpack():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None, None
        if not bool(sr.get(f"{prefix}_active", False)):
            return None, None

        expected_phase = str(sr.get(f"{prefix}_phase", "") or "").strip().upper()
        expected_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if require_phase_match and expected_phase and current_phase and expected_phase != current_phase:
            return None, None
        if expected_owner and current_owner and expected_owner != current_owner:
            return None, None
        if expected_turn and current_turn and expected_turn != current_turn:
            return None, None
        return root, sr

    def _set_soulforged_warpack_effect_state(
        self,
        unit,
        *,
        prefix: str,
        source: str,
        player=None,
        game=None,
        extra_state: Optional[dict] = None,
        track_phase: bool = True,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        if track_phase:
            sr[f"{prefix}_phase"] = self._current_phase_name(game=game)
        else:
            sr.pop(f"{prefix}_phase", None)
        sr[f"{prefix}_turn"] = self._current_turn(game=game)
        sr[f"{prefix}_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr[f"{prefix}_source"] = str(source or "").strip() or str(prefix).replace("_", " ").title()
        for key, value in dict(extra_state or {}).items():
            sr[str(key)] = value
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

    def soulforged_warpack_desperate_pledge_ap_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        _ = weapon_profile
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root, sr = self._soulforged_warpack_effect_state(
            unit,
            prefix=self._SOULFORGED_WARPACK_DESPERATE_PLEDGE_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_daemon_vehicle(root):
            return 0, ""
        contract_active, _contract_source = self._soulforged_warpack_contract_state(root, game=game)
        if not contract_active:
            return 0, ""
        try:
            bonus = int(sr.get(f"{self._SOULFORGED_WARPACK_DESPERATE_PLEDGE_PREFIX}_ap_bonus", 1) or 0)
        except (TypeError, ValueError):
            bonus = 1
        if bonus <= 0:
            return 0, ""
        source = str(
            sr.get(f"{self._SOULFORGED_WARPACK_DESPERATE_PLEDGE_PREFIX}_source", "")
            or self._SOULFORGED_WARPACK_DESPERATE_PLEDGE_SOURCE
        ).strip() or self._SOULFORGED_WARPACK_DESPERATE_PLEDGE_SOURCE
        return int(bonus), source

    def resolve_soulforged_warpack_glut_of_souls(
        self,
        unit,
        *,
        killing_models_by_target=None,
        game=None,
    ) -> dict:
        root, sr = self._soulforged_warpack_effect_state(
            unit,
            prefix=self._SOULFORGED_WARPACK_GLUT_OF_SOULS_PREFIX,
            game=game,
        )
        if root is None or sr is None:
            return {"triggered": False}
        if not self._unit_is_daemon_vehicle(root):
            return {"triggered": False}
        contract_active, _contract_source = self._soulforged_warpack_contract_state(root, game=game)
        if not contract_active:
            return {"triggered": False}
        if not isinstance(killing_models_by_target, dict):
            return {"triggered": False}

        destroyed_count = 0
        for _target_unit, models in list(killing_models_by_target.items()):
            destroyed_count += len(list(models or []))
        if destroyed_count <= 0:
            return {"triggered": False}

        try:
            threshold = int(sr.get(f"{self._SOULFORGED_WARPACK_GLUT_OF_SOULS_PREFIX}_threshold", 5) or 5)
        except (TypeError, ValueError):
            threshold = 5
        threshold = max(2, min(6, threshold))
        try:
            heal_cap = int(sr.get(f"{self._SOULFORGED_WARPACK_GLUT_OF_SOULS_PREFIX}_heal_cap", 6) or 6)
        except (TypeError, ValueError):
            heal_cap = 6
        heal_cap = max(0, heal_cap)
        try:
            already_healed = int(sr.get(f"{self._SOULFORGED_WARPACK_GLUT_OF_SOULS_PREFIX}_healed_wounds", 0) or 0)
        except (TypeError, ValueError):
            already_healed = 0
        if already_healed >= heal_cap:
            return {
                "triggered": True,
                "destroyed_models": int(destroyed_count),
                "successful_rolls": 0,
                "healed": 0,
            }

        successful_rolls = 0
        rolls: list[int] = []
        for _index in range(int(destroyed_count)):
            try:
                roll = int(get_roll("D6") or 0)
            except (TypeError, ValueError):
                roll = 0
            rolls.append(int(roll))
            if int(roll) >= int(threshold):
                successful_rolls += 1

        remaining_cap = max(0, int(heal_cap - already_healed))
        heal_amount = min(int(successful_rolls), int(remaining_cap))
        if heal_amount > 0:
            get_models = getattr(root, "get_attached_unit_models", None)
            models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
            for _index in range(int(heal_amount)):
                healed = False
                for model in list(models or []):
                    if model is None or not self._model_alive(model):
                        continue
                    try:
                        base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
                        current_wounds = int(getattr(model, "wounds", 0) or 0)
                    except (TypeError, ValueError):
                        continue
                    if current_wounds >= base_wounds:
                        continue
                    heal_fn = getattr(model, "heal", None)
                    if callable(heal_fn):
                        heal_fn(1)
                    else:
                        model.wounds = min(base_wounds, current_wounds + 1)
                    healed = True
                    break
                if not healed:
                    heal_amount = _index
                    break

        updated = dict(sr)
        updated[f"{self._SOULFORGED_WARPACK_GLUT_OF_SOULS_PREFIX}_healed_wounds"] = int(already_healed + heal_amount)
        root.special_rules = updated
        return {
            "triggered": True,
            "destroyed_models": int(destroyed_count),
            "successful_rolls": int(successful_rolls),
            "healed": int(heal_amount),
            "rolls": list(rolls),
        }

    def desperate_devotion_can_trigger(self, unit, *, action: str, game=None) -> bool:
        if not self.is_chaos_cult():
            return False
        action_key = str(action or "").strip().lower()
        if action_key not in self._DESPERATE_DEVOTION_ALLOWED_ACTIONS:
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_on_battlefield(root):
            return False
        if self._unit_arrived_from_reserves_this_turn(root):
            return False
        if not self._unit_is_damned(root):
            return False
        if not self._unit_has_dark_pacts(root):
            return False

        phase_name = self._current_phase_name(game=game)
        if action_key in {"move", "advance"}:
            return phase_name in {"", "MOVEMENT_PHASE"}
        if action_key == "charge":
            return phase_name in {"", "CHARGE_PHASE"}
        return False

    def activate_desperate_devotion(
        self,
        unit,
        *,
        action: str,
        game=None,
        player=None,
        ability_name: str = "Desperate Devotion",
    ) -> dict:
        action_key = str(action or "").strip().lower()
        root = self._unit_root(unit)
        if root is None:
            return {"ok": False, "reason": "Unit not found."}
        if not self.desperate_devotion_can_trigger(root, action=action_key, game=game):
            return {"ok": False, "reason": "Desperate Devotion cannot trigger for this unit/action."}

        leadership_fn = getattr(root, "pass_leadership_check", None)
        leadership_passed = True
        if callable(leadership_fn):
            leadership_passed = bool(leadership_fn())

        mortal_wounds = 0
        if not leadership_passed:
            try:
                mortal_wounds = int(get_roll("D3") or 0)
            except (TypeError, ValueError):
                mortal_wounds = 0
            if mortal_wounds <= 0:
                mortal_wounds = 1
            apply_mortal = getattr(root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortal):
                resolved_game = self._resolve_game(game=game)
                apply_mortal(root, int(mortal_wounds), game_map=getattr(resolved_game, "map", None))

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["chaos_cult_desperate_devotion_active"] = True
        sr["chaos_cult_desperate_devotion_phase"] = self._current_phase_name(game=game)
        sr["chaos_cult_desperate_devotion_turn"] = self._current_turn(game=game)
        sr["chaos_cult_desperate_devotion_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr["chaos_cult_desperate_devotion_move_bonus"] = 2
        sr["chaos_cult_desperate_devotion_charge_bonus"] = 2
        sr["chaos_cult_desperate_devotion_source"] = str(ability_name or "Desperate Devotion").strip() or "Desperate Devotion"
        root.special_rules = sr

        return {
            "ok": True,
            "unit_id": self._unit_root_key(root),
            "action": action_key,
            "leadership_passed": bool(leadership_passed),
            "mortal_wounds": int(mortal_wounds),
        }

    def desperate_devotion_active(self, unit, *, game=None) -> bool:
        if not self.is_chaos_cult():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("chaos_cult_desperate_devotion_active", False)):
            return False
        expected_phase = str(sr.get("chaos_cult_desperate_devotion_phase", "") or "").strip().upper()
        expected_owner = str(sr.get("chaos_cult_desperate_devotion_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get("chaos_cult_desperate_devotion_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if expected_phase and current_phase and expected_phase != current_phase:
            return False
        if expected_owner and current_owner and expected_owner != current_owner:
            return False
        if expected_turn and current_turn and expected_turn != current_turn:
            return False
        return True

    def desperate_devotion_movement_bonus(self, model=None, unit=None, *, game=None) -> tuple[int, str]:
        target_unit = self._unit_root(unit)
        if target_unit is None:
            target_unit = self._unit_root(getattr(model, "parent_unit", None))
        if target_unit is None:
            return 0, ""
        if not self.desperate_devotion_active(target_unit, game=game):
            return 0, ""
        sr = getattr(target_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return 0, ""
        try:
            bonus = int(sr.get("chaos_cult_desperate_devotion_move_bonus", 2) or 0)
        except (TypeError, ValueError):
            bonus = 0
        if bonus <= 0:
            return 0, ""
        source = str(sr.get("chaos_cult_desperate_devotion_source", "") or "Desperate Devotion").strip() or "Desperate Devotion"
        return int(bonus), source

    def desperate_devotion_charge_roll_bonus(self, unit, *, game=None) -> tuple[int, str]:
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        if not self.desperate_devotion_active(root, game=game):
            return 0, ""
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return 0, ""
        try:
            bonus = int(sr.get("chaos_cult_desperate_devotion_charge_bonus", 2) or 0)
        except (TypeError, ValueError):
            bonus = 0
        if bonus <= 0:
            return 0, ""
        source = str(sr.get("chaos_cult_desperate_devotion_source", "") or "Desperate Devotion").strip() or "Desperate Devotion"
        return int(bonus), source

    def _chaos_cult_effect_state(self, unit, *, prefix: str, game=None):
        if not self.is_chaos_cult():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None, None
        if not bool(sr.get(f"{prefix}_active", False)):
            return None, None

        expected_phase = str(sr.get(f"{prefix}_phase", "") or "").strip().upper()
        expected_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if expected_phase and current_phase and expected_phase != current_phase:
            return None, None
        if expected_owner and current_owner and expected_owner != current_owner:
            return None, None
        if expected_turn and current_turn and expected_turn != current_turn:
            return None, None
        return root, sr

    def _set_chaos_cult_effect_state(
        self,
        unit,
        *,
        prefix: str,
        source: str,
        player=None,
        game=None,
        extra_state: Optional[dict] = None,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        sr[f"{prefix}_phase"] = self._current_phase_name(game=game)
        sr[f"{prefix}_turn"] = self._current_turn(game=game)
        sr[f"{prefix}_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr[f"{prefix}_source"] = str(source or "").strip() or str(prefix).replace("_", " ").title()
        for key, value in dict(extra_state or {}).items():
            sr[str(key)] = value
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

    def _apply_chaos_cult_self_mortals(self, unit, *, roll_spec: str = "D3", game=None) -> int:
        root = self._unit_root(unit)
        if root is None:
            return 0
        try:
            mortal_wounds = int(get_roll(str(roll_spec or "D3")) or 0)
        except (TypeError, ValueError):
            mortal_wounds = 0
        if mortal_wounds <= 0:
            mortal_wounds = 1
        apply_mortal = getattr(root, "_apply_mortal_wounds_to_unit", None)
        if callable(apply_mortal):
            resolved_game = self._resolve_game(game=game)
            apply_mortal(root, int(mortal_wounds), game_map=getattr(resolved_game, "map", None))
        return int(mortal_wounds)

    def resolve_chaos_cult_desperate_pact(self, unit, *, game=None) -> dict:
        root = self._unit_root(unit)
        if root is None:
            return {"ok": False, "reason": "Unit not found."}
        leadership_fn = getattr(root, "pass_leadership_check", None)
        leadership_passed = True
        if callable(leadership_fn):
            leadership_passed = bool(leadership_fn())
        mortal_wounds = 0
        if not leadership_passed:
            mortal_wounds = self._apply_chaos_cult_self_mortals(root, roll_spec="D3", game=game)
        return {
            "ok": True,
            "unit_id": self._unit_entity_key(root),
            "leadership_passed": bool(leadership_passed),
            "mortal_wounds": int(mortal_wounds),
        }

    def _chaos_cult_effect_source(self, sr: dict, *, prefix: str, default: str) -> str:
        return str(sr.get(f"{prefix}_source", "") or default).strip() or default

    def _deceptors_effect_source(self, sr: dict, *, prefix: str, default: str) -> str:
        return str(sr.get(f"{prefix}_source", "") or default).strip() or default

    def _dread_talons_effect_source(self, sr: dict, *, prefix: str, default: str) -> str:
        return str(sr.get(f"{prefix}_source", "") or default).strip() or default

    def _deceptors_effect_state(
        self,
        unit,
        *,
        prefix: str,
        game=None,
        require_phase_match: bool = True,
    ):
        if not self.is_deceptors():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None, None
        if not bool(sr.get(f"{prefix}_active", False)):
            return None, None

        expected_phase = str(sr.get(f"{prefix}_phase", "") or "").strip().upper()
        expected_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if require_phase_match and expected_phase and current_phase and expected_phase != current_phase:
            return None, None
        if expected_owner and current_owner and expected_owner != current_owner:
            return None, None
        if expected_turn and current_turn and expected_turn != current_turn:
            return None, None
        return root, sr

    def _set_deceptors_effect_state(
        self,
        unit,
        *,
        prefix: str,
        source: str,
        player=None,
        game=None,
        extra_state: Optional[dict] = None,
        track_phase: bool = True,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        if track_phase:
            sr[f"{prefix}_phase"] = self._current_phase_name(game=game)
        else:
            sr.pop(f"{prefix}_phase", None)
        sr[f"{prefix}_turn"] = self._current_turn(game=game)
        sr[f"{prefix}_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr[f"{prefix}_source"] = str(source or "").strip() or str(prefix).replace("_", " ").title()
        for key, value in dict(extra_state or {}).items():
            sr[str(key)] = value
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

    def _dread_talons_effect_state(
        self,
        unit,
        *,
        prefix: str,
        game=None,
        require_phase_match: bool = True,
    ):
        if not self.is_dread_talons():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None, None
        if not bool(sr.get(f"{prefix}_active", False)):
            return None, None

        expected_phase = str(sr.get(f"{prefix}_phase", "") or "").strip().upper()
        expected_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if require_phase_match and expected_phase and current_phase and expected_phase != current_phase:
            return None, None
        if expected_owner and current_owner and expected_owner != current_owner:
            return None, None
        if expected_turn and current_turn and expected_turn != current_turn:
            return None, None
        return root, sr

    def _set_dread_talons_effect_state(
        self,
        unit,
        *,
        prefix: str,
        source: str,
        player=None,
        game=None,
        extra_state: Optional[dict] = None,
        track_phase: bool = True,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        if track_phase:
            sr[f"{prefix}_phase"] = self._current_phase_name(game=game)
        else:
            sr.pop(f"{prefix}_phase", None)
        sr[f"{prefix}_turn"] = self._current_turn(game=game)
        sr[f"{prefix}_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr[f"{prefix}_source"] = str(source or "").strip() or str(prefix).replace("_", " ").title()
        for key, value in dict(extra_state or {}).items():
            sr[str(key)] = value
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

    @classmethod
    def _nightmare_hunt_effect_source(cls, sr: dict, *, prefix: str, default: str) -> str:
        if not isinstance(sr, dict):
            return default
        return str(sr.get(f"{prefix}_source", "") or default).strip() or default

    def _nightmare_hunt_effect_state(
        self,
        unit,
        *,
        prefix: str,
        game=None,
        require_phase_match: bool = True,
    ):
        if not self.is_nightmare_hunt():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None, None
        if not bool(sr.get(f"{prefix}_active", False)):
            return None, None

        expected_phase = str(sr.get(f"{prefix}_phase", "") or "").strip().upper()
        expected_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if require_phase_match and expected_phase and current_phase and expected_phase != current_phase:
            return None, None
        if expected_owner and current_owner and expected_owner != current_owner:
            return None, None
        if expected_turn and current_turn and expected_turn != current_turn:
            return None, None
        return root, sr

    def _set_nightmare_hunt_effect_state(
        self,
        unit,
        *,
        prefix: str,
        source: str,
        player=None,
        game=None,
        extra_state: Optional[dict] = None,
        track_phase: bool = True,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        if track_phase:
            sr[f"{prefix}_phase"] = self._current_phase_name(game=game)
        else:
            sr.pop(f"{prefix}_phase", None)
        sr[f"{prefix}_turn"] = self._current_turn(game=game)
        sr[f"{prefix}_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr[f"{prefix}_source"] = str(source or "").strip() or str(prefix).replace("_", " ").title()
        for key, value in dict(extra_state or {}).items():
            sr[str(key)] = value
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

    @classmethod
    def _fellhammer_effect_source(cls, sr: dict, *, prefix: str, default: str) -> str:
        if not isinstance(sr, dict):
            return default
        return str(sr.get(f"{prefix}_source", "") or default).strip() or default

    def _fellhammer_effect_state(
        self,
        unit,
        *,
        prefix: str,
        game=None,
        require_phase_match: bool = True,
    ):
        if not self.is_fellhammer_siege_host():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None, None
        if not bool(sr.get(f"{prefix}_active", False)):
            return None, None

        expected_phase = str(sr.get(f"{prefix}_phase", "") or "").strip().upper()
        expected_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if require_phase_match and expected_phase and current_phase and expected_phase != current_phase:
            return None, None
        if expected_owner and current_owner and expected_owner != current_owner:
            return None, None
        if expected_turn and current_turn and expected_turn != current_turn:
            return None, None
        return root, sr

    def _set_fellhammer_effect_state(
        self,
        unit,
        *,
        prefix: str,
        source: str,
        player=None,
        game=None,
        extra_state: Optional[dict] = None,
        track_phase: bool = True,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        if track_phase:
            sr[f"{prefix}_phase"] = self._current_phase_name(game=game)
        else:
            sr.pop(f"{prefix}_phase", None)
        sr[f"{prefix}_turn"] = self._current_turn(game=game)
        sr[f"{prefix}_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr[f"{prefix}_source"] = str(source or "").strip() or str(prefix).replace("_", " ").title()
        for key, value in dict(extra_state or {}).items():
            sr[str(key)] = value
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

    @classmethod
    def _hurons_marauders_effect_source(cls, sr: dict, *, prefix: str, default: str) -> str:
        if not isinstance(sr, dict):
            return default
        return str(sr.get(f"{prefix}_source", "") or default).strip() or default

    def _hurons_marauders_until_next_turn_effect_is_expired(
        self,
        sr: dict,
        *,
        prefix: str,
        game=None,
    ) -> bool:
        if not isinstance(sr, dict):
            return True
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return False
        try:
            activation_round = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            activation_round = 0
        if activation_round <= 0:
            return False
        try:
            current_round = int(getattr(resolved_game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_round = 0
        if current_round <= activation_round:
            return False
        if current_round > activation_round + 1:
            return True

        owner_id = str(sr.get(f"{prefix}_activating_player_id", "") or "").strip()
        if not owner_id:
            return True
        owner_index = self._player_index_for_id(resolved_game, owner_id)
        if owner_index is None:
            current_owner = self._current_turn_owner_id(game=resolved_game)
            return bool(current_owner and current_owner == owner_id and self._current_phase_name(game=resolved_game))
        try:
            raw_current_index = getattr(resolved_game, "current_player_index", None)
            current_index = -1 if raw_current_index is None else int(raw_current_index)
        except (TypeError, ValueError):
            current_index = -1
        if current_index < 0:
            return False
        if current_index < owner_index:
            return False
        if current_index > owner_index:
            return True
        return bool(self._current_phase_name(game=resolved_game))

    def _hurons_marauders_effect_state(
        self,
        unit,
        *,
        prefix: str,
        game=None,
        require_phase_match: bool = True,
        until_next_turn: bool = False,
    ):
        if not self.is_hurons_marauders():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None, None
        if not bool(sr.get(f"{prefix}_active", False)):
            return None, None
        if until_next_turn:
            if self._hurons_marauders_until_next_turn_effect_is_expired(sr, prefix=prefix, game=game):
                self._remove_special_rule_prefix(root, prefix)
                return None, None
            return root, sr

        expected_phase = str(sr.get(f"{prefix}_phase", "") or "").strip().upper()
        expected_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if require_phase_match and expected_phase and current_phase and expected_phase != current_phase:
            return None, None
        if expected_owner and current_owner and expected_owner != current_owner:
            return None, None
        if expected_turn and current_turn and expected_turn != current_turn:
            return None, None
        return root, sr

    def _set_hurons_marauders_effect_state(
        self,
        unit,
        *,
        prefix: str,
        source: str,
        player=None,
        game=None,
        extra_state: Optional[dict] = None,
        track_phase: bool = True,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        if track_phase:
            sr[f"{prefix}_phase"] = self._current_phase_name(game=game)
        else:
            sr.pop(f"{prefix}_phase", None)
        sr[f"{prefix}_turn"] = self._current_turn(game=game)
        sr[f"{prefix}_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr[f"{prefix}_source"] = str(source or "").strip() or str(prefix).replace("_", " ").title()
        for key, value in dict(extra_state or {}).items():
            sr[str(key)] = value
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

    def _pactbound_effect_state(
        self,
        unit,
        *,
        prefix: str,
        game=None,
        require_phase_match: bool = True,
    ):
        if not self.is_pactbound_zealots():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None, None
        if not bool(sr.get(f"{prefix}_active", False)):
            return None, None

        expected_phase = str(sr.get(f"{prefix}_phase", "") or "").strip().upper()
        expected_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if require_phase_match and expected_phase and current_phase and expected_phase != current_phase:
            return None, None
        if expected_owner and current_owner and expected_owner != current_owner:
            return None, None
        if expected_turn and current_turn and expected_turn != current_turn:
            return None, None
        return root, sr

    def _set_pactbound_effect_state(
        self,
        unit,
        *,
        prefix: str,
        source: str,
        player=None,
        game=None,
        extra_state: Optional[dict] = None,
        track_phase: bool = True,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        if track_phase:
            sr[f"{prefix}_phase"] = self._current_phase_name(game=game)
        else:
            sr.pop(f"{prefix}_phase", None)
        sr[f"{prefix}_turn"] = self._current_turn(game=game)
        sr[f"{prefix}_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr[f"{prefix}_source"] = str(source or "").strip() or str(prefix).replace("_", " ").title()
        for key, value in dict(extra_state or {}).items():
            sr[str(key)] = value
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

    def _renegade_raiders_effect_state(
        self,
        unit,
        *,
        prefix: str,
        game=None,
        require_phase_match: bool = True,
    ):
        if not self.is_renegade_raiders():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None, None
        if not bool(sr.get(f"{prefix}_active", False)):
            return None, None

        expected_phase = str(sr.get(f"{prefix}_phase", "") or "").strip().upper()
        expected_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if require_phase_match and expected_phase and current_phase and expected_phase != current_phase:
            return None, None
        if expected_owner and current_owner and expected_owner != current_owner:
            return None, None
        if expected_turn and current_turn and expected_turn != current_turn:
            return None, None
        return root, sr

    def _set_renegade_raiders_effect_state(
        self,
        unit,
        *,
        prefix: str,
        source: str,
        player=None,
        game=None,
        extra_state: Optional[dict] = None,
        track_phase: bool = True,
    ) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_active"] = True
        if track_phase:
            sr[f"{prefix}_phase"] = self._current_phase_name(game=game)
        else:
            sr.pop(f"{prefix}_phase", None)
        sr[f"{prefix}_turn"] = self._current_turn(game=game)
        sr[f"{prefix}_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr[f"{prefix}_source"] = str(source or "").strip() or str(prefix).replace("_", " ").title()
        for key, value in dict(extra_state or {}).items():
            sr[str(key)] = value
        root.special_rules = sr
        self._clear_unit_ability_cache(root)

    @staticmethod
    def _weapon_profile_matches_attack_type(weapon_profile, attack_type: str) -> bool:
        if weapon_profile is None:
            return True
        parent = getattr(weapon_profile, "parent_wargear", None)
        if parent is None:
            return True
        if str(attack_type or "").strip().lower() == "melee":
            checker = getattr(parent, "is_melee", None)
        else:
            checker = getattr(parent, "is_ranged", None)
        return not callable(checker) or bool(checker())

    def _dread_talons_target_is_battle_shocked_or_below_half_strength(self, target_unit) -> bool:
        root = self._unit_root(target_unit)
        if root is None:
            return False
        if self._unit_is_battle_shocked(root):
            return True
        below_half = getattr(root, "is_below_half_strength", None)
        return bool(callable(below_half) and below_half())

    def deceptors_coils_of_deception_can_shoot_after_fall_back(self, unit, profile=None, *, game=None) -> bool:
        if profile is not None and not self._weapon_profile_matches_attack_type(profile, "ranged"):
            return False
        root, _sr = self._deceptors_effect_state(
            unit,
            prefix=self._DECEPTORS_COILS_OF_DECEPTION_PREFIX,
            game=game,
            require_phase_match=False,
        )
        return bool(root is not None and self._unit_is_heretic_astartes(root))

    def deceptors_from_all_sides_charge_roll_bonus(self, unit, *, game=None) -> tuple[int, str]:
        root, sr = self._deceptors_effect_state(
            unit,
            prefix=self._DECEPTORS_FROM_ALL_SIDES_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return 0, ""
        baseline = {
            str(value or "").strip()
            for value in list(sr.get(f"{self._DECEPTORS_FROM_ALL_SIDES_PREFIX}_baseline_charged_unit_ids", []) or [])
            if str(value or "").strip()
        }
        bonus = 0
        if self.army is not None:
            root_id = self._unit_entity_key(root)
            for candidate in self._iter_unique_roots(getattr(self.army, "units", []) or []):
                if candidate is None or not self._unit_is_heretic_astartes(candidate):
                    continue
                candidate_id = self._unit_entity_key(candidate)
                if not candidate_id or candidate_id == root_id or candidate_id in baseline:
                    continue
                if not bool(getattr(getattr(candidate, "round_state", None), "charged_this_round", False)):
                    continue
                bonus += 1
                if bonus >= 3:
                    break
        if bonus <= 0:
            return 0, ""
        return bonus, self._deceptors_effect_source(
            sr,
            prefix=self._DECEPTORS_FROM_ALL_SIDES_PREFIX,
            default=self._DECEPTORS_FROM_ALL_SIDES_SOURCE,
        )

    def deceptors_pick_them_off_reroll_hit_applies(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged"):
            return False, ""
        target_root = self._unit_root(target_unit)
        below_starting = getattr(target_root, "is_below_starting_strength", None) if target_root is not None else None
        if not callable(below_starting) or not bool(below_starting()):
            return False, ""
        root, sr = self._deceptors_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._DECEPTORS_PICK_THEM_OFF_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        return True, self._deceptors_effect_source(
            sr,
            prefix=self._DECEPTORS_PICK_THEM_OFF_PREFIX,
            default=self._DECEPTORS_PICK_THEM_OFF_SOURCE,
        )

    def deceptors_pick_them_off_reroll_wound_applies(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged"):
            return False, ""
        target_root = self._unit_root(target_unit)
        below_half = getattr(target_root, "is_below_half_strength", None) if target_root is not None else None
        if not callable(below_half) or not bool(below_half()):
            return False, ""
        root, sr = self._deceptors_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._DECEPTORS_PICK_THEM_OFF_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        return True, self._deceptors_effect_source(
            sr,
            prefix=self._DECEPTORS_PICK_THEM_OFF_PREFIX,
            default=self._DECEPTORS_PICK_THEM_OFF_SOURCE,
        )

    def deceptors_scrambled_coordinates_reserves_denial(self, unit, *, game=None) -> Optional[dict]:
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None or not bool(getattr(resolved_game, "reinforcements_step_active", False)):
            return None
        try:
            step_turn = int(getattr(resolved_game, "reinforcements_step_turn", 0) or 0)
        except (TypeError, ValueError):
            step_turn = 0
        try:
            current_turn = int(getattr(resolved_game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if step_turn and current_turn and step_turn != current_turn:
            return None
        step_player_id = str(getattr(resolved_game, "reinforcements_step_player_id", "") or "").strip()
        current_player = getattr(resolved_game, "get_current_player", lambda: None)()
        current_player_id = str(getattr(current_player, "id", "") or "").strip()
        if step_player_id and current_player_id and step_player_id != current_player_id:
            return None
        root, sr = self._deceptors_effect_state(
            unit,
            prefix=self._DECEPTORS_SCRAMBLED_COORDINATES_PREFIX,
            game=resolved_game,
        )
        if root is None or not self._unit_is_heretic_astartes(root) or not self._unit_on_battlefield(root):
            return None
        try:
            min_distance = float(sr.get(f"{self._DECEPTORS_SCRAMBLED_COORDINATES_PREFIX}_range", 12.0) or 12.0)
        except (TypeError, ValueError):
            min_distance = 12.0
        if min_distance <= 0.0:
            return None
        horizontal_only = bool(sr.get(f"{self._DECEPTORS_SCRAMBLED_COORDINATES_PREFIX}_horizontal_only", True))
        source_model_id = ""
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if not self._model_alive(model):
                continue
            source_model_id = str(get_entity_id(model) or "").strip()
            if source_model_id:
                break
        return {
            "range": float(min_distance),
            "horizontal_only": bool(horizontal_only),
            "source": self._deceptors_effect_source(
                sr,
                prefix=self._DECEPTORS_SCRAMBLED_COORDINATES_PREFIX,
                default=self._DECEPTORS_SCRAMBLED_COORDINATES_SOURCE,
            ),
            "source_model_id": source_model_id,
        }

    def dread_talons_depthless_cruelty_melee_ap_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "melee"):
            return 0, ""
        if not self._dread_talons_target_is_battle_shocked_or_below_half_strength(target_unit):
            return 0, ""
        root, sr = self._dread_talons_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._DREAD_TALONS_DEPTHLESS_CRUELTY_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return 0, ""
        try:
            bonus = int(sr.get(f"{self._DREAD_TALONS_DEPTHLESS_CRUELTY_PREFIX}_ap_bonus", 1) or 1)
        except (TypeError, ValueError):
            bonus = 1
        if bonus <= 0:
            return 0, ""
        return int(bonus), self._dread_talons_effect_source(
            sr,
            prefix=self._DREAD_TALONS_DEPTHLESS_CRUELTY_PREFIX,
            default=self._DREAD_TALONS_DEPTHLESS_CRUELTY_SOURCE,
        )

    def dread_talons_pitiless_hunters_reroll_hit_applies(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged"):
            return False, ""
        if not self._dread_talons_target_is_battle_shocked_or_below_half_strength(target_unit):
            return False, ""
        root, sr = self._dread_talons_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._DREAD_TALONS_PITILESS_HUNTERS_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        return True, self._dread_talons_effect_source(
            sr,
            prefix=self._DREAD_TALONS_PITILESS_HUNTERS_PREFIX,
            default=self._DREAD_TALONS_PITILESS_HUNTERS_SOURCE,
        )

    def dread_talons_pitiless_hunters_reroll_wound_applies(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged"):
            return False, ""
        if not self._dread_talons_target_is_battle_shocked_or_below_half_strength(target_unit):
            return False, ""
        root, sr = self._dread_talons_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._DREAD_TALONS_PITILESS_HUNTERS_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        return True, self._dread_talons_effect_source(
            sr,
            prefix=self._DREAD_TALONS_PITILESS_HUNTERS_PREFIX,
            default=self._DREAD_TALONS_PITILESS_HUNTERS_SOURCE,
        )

    def dread_talons_relentless_terror_can_charge_after_fall_back(self, unit, *, game=None) -> bool:
        root, _sr = self._dread_talons_effect_state(
            unit,
            prefix=self._DREAD_TALONS_RELENTLESS_TERROR_PREFIX,
            game=game,
            require_phase_match=False,
        )
        return bool(root is not None and self._unit_is_heretic_astartes(root) and self._unit_has_keyword(root, "INFANTRY"))

    def nightmare_hunt_prey_on_the_weak_reroll_hit_applies(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        _ = weapon_profile
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        if not self._dread_talons_target_is_battle_shocked_or_below_half_strength(target_unit):
            return False, ""
        root, sr = self._nightmare_hunt_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._NIGHTMARE_HUNT_PREY_ON_THE_WEAK_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        return True, self._nightmare_hunt_effect_source(
            sr,
            prefix=self._NIGHTMARE_HUNT_PREY_ON_THE_WEAK_PREFIX,
            default=self._NIGHTMARE_HUNT_PREY_ON_THE_WEAK_SOURCE,
        )

    def nightmare_hunt_talons_sunk_deep_ap_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        _ = weapon_profile
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._dread_talons_target_is_battle_shocked_or_below_half_strength(target_unit):
            return 0, ""
        root, sr = self._nightmare_hunt_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._NIGHTMARE_HUNT_TALONS_SUNK_DEEP_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return 0, ""
        try:
            bonus = int(sr.get(f"{self._NIGHTMARE_HUNT_TALONS_SUNK_DEEP_PREFIX}_ap_bonus", 1) or 1)
        except (TypeError, ValueError):
            bonus = 1
        if bonus <= 0:
            return 0, ""
        return int(bonus), self._nightmare_hunt_effect_source(
            sr,
            prefix=self._NIGHTMARE_HUNT_TALONS_SUNK_DEEP_PREFIX,
            default=self._NIGHTMARE_HUNT_TALONS_SUNK_DEEP_SOURCE,
        )

    def nightmare_hunt_relentless_terror_can_shoot_after_fall_back(self, unit, profile=None, *, game=None) -> bool:
        if profile is not None and not self._weapon_profile_matches_attack_type(profile, "ranged"):
            return False
        root, _sr = self._nightmare_hunt_effect_state(
            unit,
            prefix=self._NIGHTMARE_HUNT_RELENTLESS_TERROR_PREFIX,
            game=game,
            require_phase_match=False,
        )
        return bool(root is not None and self._unit_is_heretic_astartes(root) and self._unit_has_keyword(root, "INFANTRY"))

    def nightmare_hunt_relentless_terror_can_charge_after_fall_back(self, unit, *, game=None) -> bool:
        root, _sr = self._nightmare_hunt_effect_state(
            unit,
            prefix=self._NIGHTMARE_HUNT_RELENTLESS_TERROR_PREFIX,
            game=game,
            require_phase_match=False,
        )
        return bool(root is not None and self._unit_is_heretic_astartes(root) and self._unit_has_keyword(root, "INFANTRY"))

    def nightmare_hunt_malicious_surge_can_charge_after_advance(self, unit, *, game=None) -> bool:
        root, _sr = self._nightmare_hunt_effect_state(
            unit,
            prefix=self._NIGHTMARE_HUNT_MALICIOUS_SURGE_PREFIX,
            game=game,
        )
        return bool(root is not None and self._unit_is_heretic_astartes(root) and self._unit_has_keyword(root, "INFANTRY"))

    def fellhammer_persistent_assailants_reroll_hit_applies(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "melee"):
            return False, ""
        root, sr = self._fellhammer_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._FELLHAMMER_PERSISTENT_ASSAILANTS_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        return True, self._fellhammer_effect_source(
            sr,
            prefix=self._FELLHAMMER_PERSISTENT_ASSAILANTS_PREFIX,
            default=self._FELLHAMMER_PERSISTENT_ASSAILANTS_SOURCE,
        )

    def fellhammer_persistent_assailants_reroll_wound_applies(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "melee"):
            return False, ""
        root, sr = self._fellhammer_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._FELLHAMMER_PERSISTENT_ASSAILANTS_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        below_half = getattr(root, "is_below_half_strength", None)
        if not callable(below_half) or not bool(below_half()):
            return False, ""
        return True, self._fellhammer_effect_source(
            sr,
            prefix=self._FELLHAMMER_PERSISTENT_ASSAILANTS_PREFIX,
            default=self._FELLHAMMER_PERSISTENT_ASSAILANTS_SOURCE,
        )

    def fellhammer_pitiless_cannonade_crit_hit_threshold(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged"):
            return 0, ""
        target_root = self._unit_root(target_unit)
        below_half = getattr(target_root, "is_below_half_strength", None) if target_root is not None else None
        if not callable(below_half) or not bool(below_half()):
            return 0, ""
        root, sr = self._fellhammer_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._FELLHAMMER_PITILESS_CANNONADE_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return 0, ""
        return 5, self._fellhammer_effect_source(
            sr,
            prefix=self._FELLHAMMER_PITILESS_CANNONADE_PREFIX,
            default=self._FELLHAMMER_PITILESS_CANNONADE_SOURCE,
        )

    def fellhammer_brutal_attrition_retaliation_spec(self, unit, *, attacker_unit=None, game=None) -> Optional[dict]:
        root, sr = self._fellhammer_effect_state(
            unit,
            prefix=self._FELLHAMMER_BRUTAL_ATTRITION_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root) or not self._unit_has_keyword(root, "INFANTRY"):
            return None
        if self._unit_is_damned(root):
            return None
        attacker_root = self._unit_root(attacker_unit)
        attacker_key = self._unit_entity_key(attacker_root) if attacker_root is not None else ""
        expected_attacker_key = str(
            sr.get(f"{self._FELLHAMMER_BRUTAL_ATTRITION_PREFIX}_attacker_unit_id", "") or ""
        ).strip()
        if expected_attacker_key and attacker_key and expected_attacker_key != attacker_key:
            return None
        if expected_attacker_key and not attacker_key:
            return None
        try:
            max_rolls = int(sr.get(f"{self._FELLHAMMER_BRUTAL_ATTRITION_PREFIX}_max_rolls_per_attacker_unit", 6) or 6)
        except (TypeError, ValueError):
            max_rolls = 6
        try:
            threshold = int(sr.get(f"{self._FELLHAMMER_BRUTAL_ATTRITION_PREFIX}_threshold", 4) or 4)
        except (TypeError, ValueError):
            threshold = 4
        try:
            mortal_wounds = int(sr.get(f"{self._FELLHAMMER_BRUTAL_ATTRITION_PREFIX}_mortal_wounds", 1) or 1)
        except (TypeError, ValueError):
            mortal_wounds = 1
        if max_rolls <= 0 or threshold <= 0 or mortal_wounds <= 0:
            return None
        source = self._fellhammer_effect_source(
            sr,
            prefix=self._FELLHAMMER_BRUTAL_ATTRITION_PREFIX,
            default=self._FELLHAMMER_BRUTAL_ATTRITION_SOURCE,
        )
        return {
            "ability_key": f"allocated_melee_retaliation:{self._FELLHAMMER_BRUTAL_ATTRITION_PREFIX}",
            "source": source,
            "max_rolls_per_attacker_unit": int(max_rolls),
            "threshold": int(threshold),
            "mortal_wounds": int(mortal_wounds),
        }

    def fellhammer_siegecraft_charge_roll_penalty(self, unit, *, game=None) -> tuple[int, str]:
        root, sr = self._fellhammer_effect_state(
            unit,
            prefix=self._FELLHAMMER_SIEGECRAFT_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return 0, ""
        try:
            penalty = int(sr.get(f"{self._FELLHAMMER_SIEGECRAFT_PREFIX}_charge_penalty", 2) or 2)
        except (TypeError, ValueError):
            penalty = 2
        if penalty <= 0:
            return 0, ""
        return int(penalty), self._fellhammer_effect_source(
            sr,
            prefix=self._FELLHAMMER_SIEGECRAFT_PREFIX,
            default=self._FELLHAMMER_SIEGECRAFT_SOURCE,
        )

    def fellhammer_steadfast_determination_fnp(self, unit, *, target_model=None, game=None) -> tuple[int, str]:
        root, sr = self._fellhammer_effect_state(
            unit,
            prefix=self._FELLHAMMER_STEADFAST_DETERMINATION_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root) or self._unit_is_damned(root):
            return 0, ""
        try:
            fnp = int(sr.get(f"{self._FELLHAMMER_STEADFAST_DETERMINATION_PREFIX}_fnp", 5) or 5)
        except (TypeError, ValueError):
            fnp = 5
        if fnp <= 0:
            return 0, ""
        return int(fnp), self._fellhammer_effect_source(
            sr,
            prefix=self._FELLHAMMER_STEADFAST_DETERMINATION_PREFIX,
            default=self._FELLHAMMER_STEADFAST_DETERMINATION_SOURCE,
        )

    def can_activate_hurons_marauders_hardened_killers(self, unit, *, game=None, player=None) -> bool:
        if not self.is_hurons_marauders() or self.army is None:
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not self._unit_on_battlefield(root):
            return False
        if not self._unit_is_damned(root):
            return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        army_player = getattr(self.army, "player", None)
        if army_player is not None and str(getattr(army_player, "id", "") or "") != str(getattr(owner, "id", "") or ""):
            return False
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return False
        phase_name = self._current_phase_name(game=resolved_game)
        if phase_name and phase_name != "COMMAND_PHASE":
            return False
        current_owner = str(self._current_turn_owner_id(game=resolved_game, player=owner) or "")
        if current_owner and current_owner != str(getattr(owner, "id", "") or ""):
            return False
        return True

    def activate_hurons_marauders_hardened_killers(
        self,
        unit,
        *,
        choice_key: str,
        game=None,
        player=None,
        source: str = "",
    ) -> dict:
        root = self._unit_root(unit)
        if root is None:
            return {"ok": False, "reason": "Unit not found."}
        if not self.can_activate_hurons_marauders_hardened_killers(root, game=game, player=player):
            return {"ok": False, "reason": "Hardened Killers cannot be activated for this unit right now."}
        choice = str(choice_key or "").strip().upper()
        if choice not in {
            self._HARDENED_KILLERS_CHOICE_BALLISTIC_SKILL,
            self._HARDENED_KILLERS_CHOICE_RAPID_FIRE,
            self._HARDENED_KILLERS_CHOICE_SAVE,
        }:
            return {"ok": False, "reason": "Invalid Hardened Killers choice."}
        owner_id = self._current_turn_owner_id(game=game, player=player)
        self._set_hurons_marauders_effect_state(
            root,
            prefix=self._HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX,
            source=str(source or self._HURONS_MARAUDERS_HARDENED_KILLERS_SOURCE).strip()
            or self._HURONS_MARAUDERS_HARDENED_KILLERS_SOURCE,
            player=player,
            game=game,
            track_phase=False,
            extra_state={
                f"{self._HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX}_choice_key": choice,
                f"{self._HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX}_activating_player_id": str(owner_id or "").strip(),
            },
        )
        return {
            "ok": True,
            "unit_id": self._unit_entity_key(root),
            "choice_key": choice,
            "choice_name": self._hardened_killers_choice_label(choice),
        }

    def hurons_marauders_can_shoot_after_advance(self, unit, profile=None, *, game=None) -> bool:
        if profile is not None and not self._weapon_profile_matches_attack_type(profile, "ranged"):
            return False
        root, _sr = self._hurons_marauders_effect_state(
            unit,
            prefix=self._HURONS_MARAUDERS_AT_THE_TYRANTS_COMMAND_PREFIX,
            game=game,
            require_phase_match=False,
        )
        return bool(root is not None and self._unit_is_heretic_astartes(root))

    def hurons_marauders_can_charge_after_advance(self, unit, *, game=None) -> bool:
        root, _sr = self._hurons_marauders_effect_state(
            unit,
            prefix=self._HURONS_MARAUDERS_AT_THE_TYRANTS_COMMAND_PREFIX,
            game=game,
            require_phase_match=False,
        )
        return bool(root is not None and self._unit_is_heretic_astartes(root))

    def hurons_marauders_hardened_killers_attack_skill_override(
        self,
        model,
        *,
        attack_type: str = "any",
        weapon_profile=None,
        game=None,
    ) -> Optional[dict]:
        if model is None or not self._model_in_army(model):
            return None
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged"):
            return None
        root, sr = self._hurons_marauders_effect_state(
            getattr(model, "parent_unit", None),
            prefix=self._HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX,
            game=game,
            require_phase_match=False,
            until_next_turn=True,
        )
        if root is None or not self._unit_is_damned(root):
            return None
        choice_key = str(
            sr.get(f"{self._HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX}_choice_key", "") or ""
        ).strip().upper()
        if choice_key != self._HARDENED_KILLERS_CHOICE_BALLISTIC_SKILL:
            return None
        try:
            base_value = int(getattr(weapon_profile, "skill", 0) or 0)
        except (TypeError, ValueError):
            base_value = 0
        if base_value <= 0:
            return None
        improved_value = max(2, int(base_value) - 1)
        if improved_value >= int(base_value):
            return None
        source = self._hurons_marauders_effect_source(
            sr,
            prefix=self._HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX,
            default=self._HURONS_MARAUDERS_HARDENED_KILLERS_SOURCE,
        )
        return {
            "value": int(improved_value),
            "source": source,
            "attack_type": "ranged",
            "source_model_id": str(get_entity_id(model) or ""),
        }

    def hurons_marauders_hardened_killers_save_override(self, unit, model=None, *, game=None) -> tuple[Optional[int], Optional[str]]:
        if model is None:
            return None, None
        if not self._model_in_army(model):
            return None, None
        root, sr = self._hurons_marauders_effect_state(
            unit,
            prefix=self._HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX,
            game=game,
            require_phase_match=False,
            until_next_turn=True,
        )
        if root is None or not self._unit_is_damned(root):
            return None, None
        choice_key = str(
            sr.get(f"{self._HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX}_choice_key", "") or ""
        ).strip().upper()
        if choice_key != self._HARDENED_KILLERS_CHOICE_SAVE:
            return None, None
        try:
            base_save = int(getattr(model, "save", 0) or 0)
        except (TypeError, ValueError):
            base_save = 0
        if base_save <= 0:
            return None, None
        improved_save = max(2, int(base_save) - 1)
        if improved_save >= int(base_save):
            return None, None
        source = self._hurons_marauders_effect_source(
            sr,
            prefix=self._HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX,
            default=self._HURONS_MARAUDERS_HARDENED_KILLERS_SOURCE,
        )
        return int(improved_save), source

    def hurons_marauders_hardened_killers_rapid_fire_attacks_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        root, sr = self._hurons_marauders_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX,
            game=game,
            require_phase_match=False,
            until_next_turn=True,
        )
        if root is None or not self._unit_is_damned(root):
            return 0, ""
        choice_key = str(
            sr.get(f"{self._HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX}_choice_key", "") or ""
        ).strip().upper()
        if choice_key != self._HARDENED_KILLERS_CHOICE_RAPID_FIRE:
            return 0, ""
        rapid_fire_check = getattr(weapon_profile, "is_rapid_fire", None) if weapon_profile is not None else None
        if not callable(rapid_fire_check) or not bool(rapid_fire_check()):
            return 0, ""
        return 1, self._hurons_marauders_effect_source(
            sr,
            prefix=self._HURONS_MARAUDERS_HARDENED_KILLERS_PREFIX,
            default=self._HURONS_MARAUDERS_HARDENED_KILLERS_SOURCE,
        )

    def hurons_marauders_reavers_flurry_melee_attacks_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "melee"):
            return 0, ""
        root, sr = self._hurons_marauders_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._HURONS_MARAUDERS_REAVERS_FLURRY_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return 0, ""
        try:
            bonus = int(sr.get(f"{self._HURONS_MARAUDERS_REAVERS_FLURRY_PREFIX}_attacks_bonus", 1) or 0)
        except (TypeError, ValueError):
            bonus = 0
        if bonus <= 0:
            return 0, ""
        return int(bonus), self._hurons_marauders_effect_source(
            sr,
            prefix=self._HURONS_MARAUDERS_REAVERS_FLURRY_PREFIX,
            default=self._HURONS_MARAUDERS_REAVERS_FLURRY_SOURCE,
        )

    def chaos_cult_chosen_for_glory_reroll_hit_applies(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged") and not self._weapon_profile_matches_attack_type(
            weapon_profile,
            "melee",
        ):
            return False, ""
        root, sr = self._chaos_cult_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._CHAOS_CULT_CHOSEN_FOR_GLORY_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_damned(root):
            return False, ""
        return True, self._chaos_cult_effect_source(
            sr,
            prefix=self._CHAOS_CULT_CHOSEN_FOR_GLORY_PREFIX,
            default=self._CHAOS_CULT_CHOSEN_FOR_GLORY_SOURCE,
        )

    def chaos_cult_chosen_for_glory_reroll_wound_applies(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        root, sr = self._chaos_cult_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._CHAOS_CULT_CHOSEN_FOR_GLORY_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_damned(root):
            return False, ""
        if not bool(sr.get(f"{self._CHAOS_CULT_CHOSEN_FOR_GLORY_PREFIX}_leadership_passed", False)):
            return False, ""
        return True, self._chaos_cult_effect_source(
            sr,
            prefix=self._CHAOS_CULT_CHOSEN_FOR_GLORY_PREFIX,
            default=self._CHAOS_CULT_CHOSEN_FOR_GLORY_SOURCE,
        )

    def chaos_cult_crazed_focus_ranged_ap_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged"):
            return 0, ""
        root, sr = self._chaos_cult_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._CHAOS_CULT_CRAZED_FOCUS_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_damned(root):
            return 0, ""
        return 1, self._chaos_cult_effect_source(
            sr,
            prefix=self._CHAOS_CULT_CRAZED_FOCUS_PREFIX,
            default=self._CHAOS_CULT_CRAZED_FOCUS_SOURCE,
        )

    def chaos_cult_crazed_focus_ranged_strength_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "ranged"):
            return 0, ""
        root, sr = self._chaos_cult_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._CHAOS_CULT_CRAZED_FOCUS_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_damned(root):
            return 0, ""
        if not bool(sr.get(f"{self._CHAOS_CULT_CRAZED_FOCUS_PREFIX}_leadership_passed", False)):
            return 0, ""
        return 1, self._chaos_cult_effect_source(
            sr,
            prefix=self._CHAOS_CULT_CRAZED_FOCUS_PREFIX,
            default=self._CHAOS_CULT_CRAZED_FOCUS_SOURCE,
        )

    def chaos_cult_infernal_sacrifice_melee_attacks_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "melee"):
            return 0, ""
        root, sr = self._chaos_cult_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._CHAOS_CULT_INFERNAL_SACRIFICE_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_damned(root):
            return 0, ""
        return 1, self._chaos_cult_effect_source(
            sr,
            prefix=self._CHAOS_CULT_INFERNAL_SACRIFICE_PREFIX,
            default=self._CHAOS_CULT_INFERNAL_SACRIFICE_SOURCE,
        )

    def chaos_cult_infernal_sacrifice_melee_strength_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "melee"):
            return 0, ""
        root, sr = self._chaos_cult_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._CHAOS_CULT_INFERNAL_SACRIFICE_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_damned(root):
            return 0, ""
        if not bool(sr.get(f"{self._CHAOS_CULT_INFERNAL_SACRIFICE_PREFIX}_leadership_passed", False)):
            return 0, ""
        return 1, self._chaos_cult_effect_source(
            sr,
            prefix=self._CHAOS_CULT_INFERNAL_SACRIFICE_PREFIX,
            default=self._CHAOS_CULT_INFERNAL_SACRIFICE_SOURCE,
        )

    def _chaos_cult_resolve_unit_from_key(self, unit_key: str, *, game=None, game_map=None):
        resolved_key = str(unit_key or "").strip()
        if not resolved_key:
            return None
        resolved_game = self._resolve_game(game=game)
        if game_map is None and resolved_game is not None:
            game_map = getattr(resolved_game, "map", None)
        if game_map is None:
            return None
        for unit in list(getattr(game_map, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            if self._unit_entity_key(root) == resolved_key:
                return root
        return None

    def chaos_cult_mortal_thralls_support_unit(
        self,
        protected_unit,
        *,
        attacker_unit=None,
        game=None,
        game_map=None,
    ) -> tuple[Optional[object], str]:
        root, sr = self._chaos_cult_effect_state(
            protected_unit,
            prefix=self._CHAOS_CULT_MORTAL_THRALLS_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return None, ""
        expected_attacker_key = str(sr.get(f"{self._CHAOS_CULT_MORTAL_THRALLS_PREFIX}_attacker_unit_id", "") or "").strip()
        current_attacker_key = self._unit_entity_key(attacker_unit)
        if expected_attacker_key and current_attacker_key and expected_attacker_key != current_attacker_key:
            return None, ""
        support_key = str(sr.get(f"{self._CHAOS_CULT_MORTAL_THRALLS_PREFIX}_support_unit_id", "") or "").strip()
        support_root = self._chaos_cult_resolve_unit_from_key(support_key, game=game, game_map=game_map)
        if support_root is None or not self._unit_in_army(support_root):
            return None, ""
        if not self._unit_is_damned(support_root) or not self._unit_on_battlefield(support_root):
            return None, ""
        return support_root, self._chaos_cult_effect_source(
            sr,
            prefix=self._CHAOS_CULT_MORTAL_THRALLS_PREFIX,
            default=self._CHAOS_CULT_MORTAL_THRALLS_SOURCE,
        )

    def chaos_cult_selfless_demise_applies(self, unit, *, attacker_unit=None, game=None) -> tuple[bool, str]:
        root, sr = self._chaos_cult_effect_state(
            unit,
            prefix=self._CHAOS_CULT_SELFLESS_DEMISE_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_damned(root):
            return False, ""
        expected_attacker_key = str(sr.get(f"{self._CHAOS_CULT_SELFLESS_DEMISE_PREFIX}_attacker_unit_id", "") or "").strip()
        current_attacker_key = self._unit_entity_key(attacker_unit)
        if expected_attacker_key and current_attacker_key and expected_attacker_key != current_attacker_key:
            return False, ""
        return True, self._chaos_cult_effect_source(
            sr,
            prefix=self._CHAOS_CULT_SELFLESS_DEMISE_PREFIX,
            default=self._CHAOS_CULT_SELFLESS_DEMISE_SOURCE,
        )

    @staticmethod
    def _model_alive(model) -> bool:
        if model is None:
            return False
        alive_attr = getattr(model, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    @staticmethod
    def _model_name(model) -> str:
        return str(getattr(model, "name", "") or "").strip()

    @classmethod
    def _is_dark_disciple_model(cls, model) -> bool:
        return cls._normalize_name(cls._model_name(model)) in {"dark disciple", "dark disciples"}

    @staticmethod
    def _model_has_keyword(model, keyword: str) -> bool:
        if model is None:
            return False
        target_kw = str(keyword or "").strip().lower()
        if not target_kw:
            return False
        check_any = getattr(model, "has_any_keyword", None)
        if callable(check_any) and bool(check_any(keyword)):
            return True
        check = getattr(model, "has_keyword", None)
        if callable(check) and bool(check(keyword)):
            return True
        keywords = list(getattr(model, "keywords", []) or [])
        faction_keywords = list(getattr(model, "faction_keywords", []) or [])
        for value in list(keywords) + list(faction_keywords):
            if str(value or "").strip().lower() == target_kw:
                return True
        return False

    def _find_enhancement_bearer_on_member(self, member, sr: dict):
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
        if bearer_id:
            for model in list(getattr(member, "models", []) or []):
                model_entity_id = str(get_entity_id(model) or "").strip()
                model_local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                if bearer_id == model_entity_id or bearer_id == model_local_id:
                    return model
        get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            return get_bearer()
        return None

    def _chaos_cult_enhancement_source_member(self, unit, *, flag_key: str):
        if not self.is_chaos_cult():
            return None, None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None, None
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
                continue
            bearer = self._find_enhancement_bearer_on_member(member, sr)
            if not self._model_alive(bearer):
                continue
            return member, sr, bearer
        return None, None, None

    def _chaos_cult_cultists_brand_condition_met(
        self,
        root,
        *,
        bearer,
        required_keyword: str,
        excluded_model_names: tuple[str, ...],
    ) -> bool:
        if root is None or bearer is None:
            return False
        bearer_id = str(get_entity_id(bearer) or "")
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        excluded = {self._normalize_name(name) for name in list(excluded_model_names or ()) if str(name or "").strip()}
        for model in list(models or []):
            if model is None or not self._model_alive(model):
                continue
            model_id = str(get_entity_id(model) or "")
            if bearer_id and model_id == bearer_id:
                continue
            if self._normalize_name(self._model_name(model)) in excluded or self._is_dark_disciple_model(model):
                continue
            if not self._model_has_keyword(model, required_keyword):
                return False
        return True

    def _chaos_cult_cultists_brand_reroll_applies(self, unit, *, reroll_key: str) -> bool:
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        source_member, source_sr, bearer = self._chaos_cult_enhancement_source_member(
            root,
            flag_key="enhancement_cultists_brand",
        )
        if source_member is None or source_sr is None or bearer is None:
            return False
        if not bool(source_sr.get(reroll_key, True)):
            return False
        required_keyword = str(
            source_sr.get("enhancement_cultists_brand_required_keyword", "DAMNED") or "DAMNED"
        ).strip().upper()
        if not required_keyword:
            required_keyword = "DAMNED"
        excluded_model_names = tuple(
            str(name or "").strip()
            for name in list(
                source_sr.get(
                    "enhancement_cultists_brand_excluded_model_names",
                    ("Dark Disciple", "Dark Disciples"),
                )
                or ()
            )
            if str(name or "").strip()
        )
        return bool(
            self._chaos_cult_cultists_brand_condition_met(
                root,
                bearer=bearer,
                required_keyword=required_keyword,
                excluded_model_names=excluded_model_names,
            )
        )

    def chaos_cult_cultists_brand_reroll_advance_applies(self, unit, *, game=None) -> bool:
        _ = game
        return bool(
            self._chaos_cult_cultists_brand_reroll_applies(
                unit,
                reroll_key="enhancement_cultists_brand_reroll_advance",
            )
        )

    def chaos_cult_cultists_brand_reroll_charge_applies(self, unit, *, game=None) -> bool:
        _ = game
        return bool(
            self._chaos_cult_cultists_brand_reroll_applies(
                unit,
                reroll_key="enhancement_cultists_brand_reroll_charge",
            )
        )

    def _chaos_cult_incendiary_goad_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        for_attacks: bool,
    ) -> tuple[int, str]:
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee = getattr(parent, "is_melee", None) if parent is not None else None
            if not callable(is_melee) or not bool(is_melee()):
                return 0, ""
        root = self._unit_root(getattr(attacker_model, "parent_unit", None))
        if root is None or not self._unit_in_army(root):
            return 0, ""
        _source_member, source_sr, _bearer = self._chaos_cult_enhancement_source_member(
            root,
            flag_key="enhancement_incendiary_goad",
        )
        if source_sr is None:
            return 0, ""
        required_keyword = str(
            source_sr.get("enhancement_incendiary_goad_required_model_keyword", "DAMNED") or "DAMNED"
        ).strip().upper()
        if required_keyword and not self._model_has_keyword(attacker_model, required_keyword):
            return 0, ""
        if bool(source_sr.get("enhancement_incendiary_goad_requires_below_starting_strength", True)):
            below_starting_fn = getattr(root, "is_below_starting_strength", None)
            if not callable(below_starting_fn) or not bool(below_starting_fn()):
                return 0, ""
        if for_attacks and bool(
            source_sr.get("enhancement_incendiary_goad_requires_below_half_strength_for_attacks", True)
        ):
            below_half_fn = getattr(root, "is_below_half_strength", None)
            if not callable(below_half_fn) or not bool(below_half_fn()):
                return 0, ""
        bonus_key = (
            "enhancement_incendiary_goad_melee_attacks_bonus"
            if for_attacks
            else "enhancement_incendiary_goad_melee_strength_bonus"
        )
        try:
            bonus = int(source_sr.get(bonus_key, 0) or 0)
        except (TypeError, ValueError):
            bonus = 0
        if bonus <= 0:
            return 0, ""
        source = str(source_sr.get("enhancement_incendiary_goad_source", "") or "Incendiary Goad").strip()
        return int(bonus), (source or "Incendiary Goad")

    def chaos_cult_incendiary_goad_melee_strength_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        _ = game
        return self._chaos_cult_incendiary_goad_bonus(
            attacker_model,
            weapon_profile=weapon_profile,
            for_attacks=False,
        )

    def chaos_cult_incendiary_goad_melee_attacks_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        _ = game
        return self._chaos_cult_incendiary_goad_bonus(
            attacker_model,
            weapon_profile=weapon_profile,
            for_attacks=True,
        )

    @staticmethod
    def _is_traitor_guardsmen_squad(unit) -> bool:
        name = str(getattr(unit, "name", "") or "").strip().lower()
        return name == "traitor guardsmen squad"

    @staticmethod
    def _unit_has_battleline_keyword(unit) -> bool:
        keywords = list(getattr(unit, "keywords", []) or [])
        for keyword in keywords:
            if str(keyword or "").strip().lower() == "battleline":
                return True
        return False

    def apply_chaos_cult_traitor_guardsmen_battleline_keywords(self, unit=None) -> None:
        if not self.is_chaos_cult():
            return
        units = [unit] if unit is not None else list(getattr(self.army, "units", []) or [])
        for root in self._iter_unique_roots(units):
            if not self._is_traitor_guardsmen_squad(root):
                continue
            if self._unit_has_battleline_keyword(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            keywords.append("Battleline")
            root.keywords = keywords

    @classmethod
    def _is_lord_discordant_unit(cls, unit) -> bool:
        return cls._normalize_name(str(getattr(unit, "name", "") or "")) in {
            "lord discordant",
            "lord discordant on helstalker",
        }

    @classmethod
    def _is_vashtorr_the_arkifane_unit(cls, unit) -> bool:
        return cls._normalize_name(str(getattr(unit, "name", "") or "")) == "vashtorr the arkifane"

    @classmethod
    def _is_warpsmith_unit(cls, unit) -> bool:
        return cls._normalize_name(str(getattr(unit, "name", "") or "")) == "warpsmith"

    def _grant_unit_ability_keywords(self, unit, *, keywords: Iterable[str]) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        updated = dict(sr)
        existing = [
            str(value or "").strip()
            for value in list(updated.get("ability_added_keywords", []) or [])
            if str(value or "").strip()
        ]
        seen = {value.lower() for value in existing}
        changed = False
        for keyword in list(keywords or ()):
            token = str(keyword or "").strip().upper()
            if not token or token.lower() in seen:
                continue
            existing.append(token)
            seen.add(token.lower())
            changed = True
        if not changed:
            return False
        updated["ability_added_keywords"] = existing
        root.special_rules = updated
        self._clear_unit_ability_cache(root)
        return True

    def _cult_of_the_arkifane_vehicle_daemon_keyword_eligible(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not self._unit_is_heretic_astartes(root):
            return False
        return bool(self._unit_has_keyword(root, "VEHICLE"))

    def _cult_of_the_arkifane_soul_forge_keyword_eligible(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if self._cult_of_the_arkifane_vehicle_daemon_keyword_eligible(root):
            return True
        return bool(
            self._is_lord_discordant_unit(root)
            or self._is_vashtorr_the_arkifane_unit(root)
        )

    def apply_cult_of_the_arkifane_keywords(self, unit=None) -> None:
        if not self.is_cult_of_the_arkifane():
            return
        units = [unit] if unit is not None else list(getattr(self.army, "units", []) or [])
        for root in self._iter_unique_roots(units):
            keywords_to_add: list[str] = []
            if self._cult_of_the_arkifane_vehicle_daemon_keyword_eligible(root):
                keywords_to_add.append("DAEMON")
            if self._cult_of_the_arkifane_soul_forge_keyword_eligible(root):
                keywords_to_add.append("SOUL FORGE")
            if keywords_to_add:
                self._grant_unit_ability_keywords(root, keywords=keywords_to_add)

    def cult_of_the_arkifane_invulnerable_save(self, target_model, *, attack_type: str = "") -> tuple[int, str]:
        _ = attack_type
        if not self.is_cult_of_the_arkifane():
            return 0, ""
        if target_model is None or not self._model_in_army(target_model):
            return 0, ""
        root = self._unit_root(getattr(target_model, "parent_unit", None))
        if root is None or not self._unit_has_keyword(root, "SOUL FORGE"):
            return 0, ""
        return 5, self._CULT_OF_THE_ARKIFANE_SOUL_FORGE_SOURCE

    def cult_of_the_arkifane_mark_of_the_soul_forges_crit_hit_threshold(
        self,
        attacker_model,
        *,
        weapon_profile=None,
    ) -> tuple[int, str]:
        _ = weapon_profile
        if not self.is_cult_of_the_arkifane():
            return 0, ""
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        root = self._unit_root(getattr(attacker_model, "parent_unit", None))
        if root is None:
            return 0, ""
        _member, source_sr, bearer = self._cult_of_the_arkifane_enhancement_source_member(
            root,
            flag_key="enhancement_mark_of_the_soul_forges",
            require_bearer_alive=True,
            require_bearer_on_battlefield=False,
        )
        if not isinstance(source_sr, dict) or not self._model_matches_bearer(attacker_model, bearer):
            return 0, ""
        try:
            threshold = int(source_sr.get("enhancement_mark_of_the_soul_forges_crit_hit_threshold", 5) or 5)
        except (TypeError, ValueError):
            threshold = 5
        threshold = int(min(6, max(2, threshold)))
        source = str(
            source_sr.get("enhancement_mark_of_the_soul_forges_source", "") or "Mark of the Soul Forges"
        ).strip() or "Mark of the Soul Forges"
        return threshold, source

    def cult_of_the_arkifane_crown_of_worms_range_bonus(self, unit, *, source_model=None) -> tuple[float, str]:
        if not self.is_cult_of_the_arkifane():
            return 0.0, ""
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return 0.0, ""
        if not (self._is_warpsmith_unit(root) or self._unit_has_keyword(root, "WARPSMITH")):
            return 0.0, ""
        _member, source_sr, bearer = self._cult_of_the_arkifane_enhancement_source_member(
            root,
            flag_key="enhancement_crown_of_worms",
            require_bearer_alive=True,
            require_bearer_on_battlefield=True,
        )
        if not isinstance(source_sr, dict):
            return 0.0, ""
        if source_model is not None and not self._model_matches_bearer(source_model, bearer):
            return 0.0, ""
        try:
            range_bonus = float(source_sr.get("enhancement_crown_of_worms_range_bonus", 3.0) or 3.0)
        except (TypeError, ValueError):
            range_bonus = 3.0
        if range_bonus <= 0.0:
            return 0.0, ""
        source = str(source_sr.get("enhancement_crown_of_worms_source", "") or "Crown of Worms").strip()
        return float(range_bonus), (source or "Crown of Worms")

    @classmethod
    def _is_legionaries_unit(cls, unit) -> bool:
        return cls._normalize_name(str(getattr(unit, "name", "") or "")) == "legionaries"

    @classmethod
    def _is_cultist_mob_unit(cls, unit) -> bool:
        return cls._normalize_name(str(getattr(unit, "name", "") or "")) == "cultist mob"

    @classmethod
    def _is_chosen_unit(cls, unit) -> bool:
        return cls._normalize_name(str(getattr(unit, "name", "") or "")) == "chosen"

    @classmethod
    def _masters_of_misdirection_unit_kind(cls, unit) -> str:
        if cls._is_legionaries_unit(unit):
            return "legionaries"
        if cls._is_cultist_mob_unit(unit):
            return "cultist_mob"
        return ""

    def _masters_of_misdirection_candidates(self) -> list:
        if self.army is None:
            return []
        candidates = []
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            if not self._unit_in_army(root):
                continue
            kind = self._masters_of_misdirection_unit_kind(root)
            if not kind:
                continue
            candidates.append((kind, root))
        candidates.sort(
            key=lambda entry: (
                0 if entry[0] == "legionaries" else 1,
                self._normalize_name(getattr(entry[1], "name", "")),
                str(get_entity_id(entry[1]) or self._unit_root_key(entry[1])),
            )
        )
        return [unit for _kind, unit in candidates]

    def masters_of_misdirection_max_units_per_type(self, *, game=None) -> int:
        size_name = ""
        if game is not None:
            battlefield = getattr(game, "battlefield", None)
            size = getattr(battlefield, "size", None)
            size_name = str(getattr(size, "name", size) or "")
        size_key = str(size_name or "").strip().upper().replace(" ", "_")
        if "INCURSION" in size_key:
            return 2
        if "ONSLAUGHT" in size_key:
            return 4
        return 3

    def _pending_masters_of_misdirection_request(self, game, *, army_id: str) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS

        target_army_id = str(army_id or "")
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != self._MASTERS_OF_MISDIRECTION_SELECTION_ABILITY:
                continue
            if target_army_id and str(ctx.get("army_id", "") or "") != target_army_id:
                continue
            return True
        return False

    def queue_masters_of_misdirection_selection_request(self, *, game=None, player=None) -> None:
        if not self.is_deceptors():
            return
        if self.army is None:
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if self._masters_of_misdirection_selection_resolved:
            return

        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
        from ..engine.decisions import DecisionOption, DecisionRequest

        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        candidates = list(self._masters_of_misdirection_candidates() or [])
        if not candidates:
            self._masters_of_misdirection_selection_resolved = True
            self.masters_of_misdirection_selected_unit_ids = set()
            return
        army_id = str(get_entity_id(self.army) or "")
        if self._pending_masters_of_misdirection_request(game, army_id=army_id):
            return

        candidate_ids = [str(get_entity_id(unit) or "") for unit in candidates if str(get_entity_id(unit) or "")]
        if not candidate_ids:
            self._masters_of_misdirection_selection_resolved = True
            self.masters_of_misdirection_selected_unit_ids = set()
            return

        max_per_type = int(self.masters_of_misdirection_max_units_per_type(game=game) or 0)
        if max_per_type <= 0:
            self._masters_of_misdirection_selection_resolved = True
            self.masters_of_misdirection_selected_unit_ids = set()
            return

        request = DecisionRequest.create(
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            "Masters of Misdirection: select eligible LEGIONARIES and CULTIST MOB units to gain Infiltrators.",
            player_id=getattr(owner, "id", None),
            options=[
                DecisionOption.create("Confirm", payload={"action": "confirm"}),
                DecisionOption.create("None", payload={"action": "skip"}),
            ],
            context={
                "army_id": army_id,
                "ability": self._MASTERS_OF_MISDIRECTION_SELECTION_ABILITY,
                "ability_name": self._MASTERS_OF_MISDIRECTION_SOURCE,
                "phase": "Declare Battle Formations step",
                "max_units": int(max_per_type * 2),
                "max_units_per_type": int(max_per_type),
                "allowed_unit_ids": list(candidate_ids),
                "title": self._MASTERS_OF_MISDIRECTION_SOURCE,
                "subtitle": (
                    f"Select up to {int(max_per_type)} LEGIONARIES and up to {int(max_per_type)} CULTIST MOB units."
                ),
                "instruction": (
                    "Selected units, and attached non-EPIC HERO CHARACTER units, gain Infiltrators until end of battle."
                ),
                "skip_label": "None (do not select units)",
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)

    def masters_of_misdirection_selection_is_valid(self, unit_ids, *, game=None) -> tuple[bool, str]:
        if not self.is_deceptors():
            return False, "Masters of Misdirection requires the Deceptors detachment."
        if unit_ids is None:
            return True, ""
        if not isinstance(unit_ids, list):
            return False, "Masters of Misdirection selection requires unit_ids."
        selected = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        max_per_type = int(self.masters_of_misdirection_max_units_per_type(game=game) or 0)
        if max_per_type <= 0:
            return False, "Masters of Misdirection selection limits are unavailable."
        if len(selected) > int(max_per_type * 2):
            return False, "Masters of Misdirection selected too many units."

        candidates_by_id = {
            str(get_entity_id(unit) or ""): unit
            for unit in list(self._masters_of_misdirection_candidates() or [])
            if str(get_entity_id(unit) or "")
        }
        legionaries_count = 0
        cultist_count = 0
        for unit_id in selected:
            root = candidates_by_id.get(unit_id)
            if root is None:
                return False, "Masters of Misdirection selection contains an ineligible unit."
            kind = self._masters_of_misdirection_unit_kind(root)
            if kind == "legionaries":
                legionaries_count += 1
            elif kind == "cultist_mob":
                cultist_count += 1
            else:
                return False, "Masters of Misdirection selection contains an ineligible unit."
        if legionaries_count > max_per_type:
            return False, f"Masters of Misdirection can select at most {max_per_type} Legionaries units."
        if cultist_count > max_per_type:
            return False, f"Masters of Misdirection can select at most {max_per_type} Cultist Mob units."
        return True, ""

    def apply_masters_of_misdirection_selection(self, unit_ids, *, game=None) -> list[str]:
        selected = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        valid, _reason = self.masters_of_misdirection_selection_is_valid(selected, game=game)
        if not valid:
            return []

        all_roots = self._iter_unique_roots(getattr(self.army, "units", []) or []) if self.army is not None else []
        for root in all_roots:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            updated = dict(sr)
            updated.pop("masters_of_misdirection_infiltrators", None)
            updated.pop("masters_of_misdirection_source", None)
            if updated != sr:
                root.special_rules = updated
                self._clear_unit_ability_cache(root)

        candidates_by_id = {
            str(get_entity_id(unit) or ""): unit
            for unit in list(self._masters_of_misdirection_candidates() or [])
            if str(get_entity_id(unit) or "")
        }
        applied_ids: list[str] = []
        for unit_id in selected:
            root = candidates_by_id.get(unit_id)
            if root is None:
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            updated = dict(sr)
            updated["masters_of_misdirection_infiltrators"] = True
            updated["masters_of_misdirection_source"] = self._MASTERS_OF_MISDIRECTION_SOURCE
            root.special_rules = updated
            self._clear_unit_ability_cache(root)
            applied_ids.append(unit_id)

        self.masters_of_misdirection_selected_unit_ids = set(applied_ids)
        self._masters_of_misdirection_selection_resolved = True
        if self.army is not None:
            setattr(self.army, "masters_of_misdirection_selected_unit_ids", list(applied_ids))
        return list(applied_ids)

    def _pending_deceptors_choose_quarry_request(
        self,
        game,
        *,
        ability: str,
        army_id: str = "",
        source_unit_id: str = "",
    ) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        ability_key = str(ability or "").strip().lower()
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != ability_key:
                continue
            if army_id and str(ctx.get("army_id", "") or "") != str(army_id):
                continue
            if source_unit_id and str(ctx.get("source_unit_id", "") or "") != str(source_unit_id):
                continue
            return True
        return False

    def _deceptors_sources_by_flag(self, *, flag_key: str, require_alive_bearer: bool = True) -> list[tuple]:
        if not self.is_deceptors() or self.army is None:
            return []
        out: list[tuple] = []
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            if root is None or not self._unit_in_army(root):
                continue
            get_members = getattr(root, "get_attached_unit_members", None)
            members = list(get_members() or []) if callable(get_members) else [root]
            if not members:
                members = [root]
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict) or not bool(sr.get(flag_key, False)):
                    continue
                bearer = self._find_enhancement_bearer_on_member(member, sr)
                if bool(require_alive_bearer) and not self._model_alive(bearer):
                    continue
                out.append((root, member, sr, bearer))
                break
        out.sort(key=lambda entry: str(get_entity_id(entry[0]) or self._unit_root_key(entry[0])))
        return out

    def _deceptors_source_entry(self, source_unit_id: str, *, flag_key: str):
        target_id = str(source_unit_id or "").strip()
        if not target_id:
            return None
        for entry in self._deceptors_sources_by_flag(flag_key=flag_key):
            root = entry[0]
            rid = str(get_entity_id(root) or "")
            if rid == target_id:
                return entry
        return None

    def _deceptors_unit_by_id(self, unit_id: str):
        target_id = str(unit_id or "").strip()
        if not target_id or self.army is None:
            return None
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            if root is None:
                continue
            if str(get_entity_id(root) or "") == target_id:
                return root
        return None

    def _deceptors_model_by_id(self, model_id: str):
        target_id = str(model_id or "").strip()
        if not target_id or self.army is None:
            return None
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            if root is None:
                continue
            get_members = getattr(root, "get_attached_unit_members", None)
            members = list(get_members() or []) if callable(get_members) else [root]
            if not members:
                members = [root]
            for member in members:
                for model in list(getattr(member, "models", []) or []):
                    model_eid = str(get_entity_id(model) or "")
                    model_lid = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                    if target_id in {model_eid, model_lid}:
                        return model
        return None

    def can_select_deceptors_falsehood_declare(self, source_unit_id: str, *, game=None, player=None) -> bool:
        if not self.is_deceptors() or self.army is None:
            return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        army_player = getattr(self.army, "player", None)
        if army_player is not None and str(getattr(army_player, "id", "") or "") != str(getattr(owner, "id", "") or ""):
            return False
        entry = self._deceptors_source_entry(source_unit_id, flag_key="enhancement_falsehood")
        if entry is None:
            return False
        _root, _member, sr, _bearer = entry
        if not isinstance(sr, dict):
            return False
        if bool(sr.get("enhancement_falsehood_declare_resolved", False)):
            return False
        return True

    def queue_deceptors_falsehood_declare_request(self, *, game=None, player=None) -> None:
        if not self.is_deceptors() or self.army is None:
            return
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None or not bool(getattr(resolved_game, "is_authoritative", True)):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        army_id = str(get_entity_id(self.army) or "")
        for root, member, sr, bearer in self._deceptors_sources_by_flag(flag_key="enhancement_falsehood"):
            source_unit_id = str(get_entity_id(root) or "")
            if not source_unit_id:
                continue
            if not self.can_select_deceptors_falsehood_declare(source_unit_id, game=resolved_game, player=owner):
                continue
            if self._pending_deceptors_choose_quarry_request(
                resolved_game,
                ability=self._DECEPTORS_FALSEHOOD_DECLARE_ABILITY,
                army_id=army_id,
                source_unit_id=source_unit_id,
            ):
                continue
            source_model_id = str(get_entity_id(bearer) or getattr(bearer, "id", getattr(bearer, "_id", "")) or "")
            options = [
                DecisionOption.create(
                    "Deploy normally",
                    payload={
                        "choice_key": "DEPLOY",
                        "source_unit_id": source_unit_id,
                        "source_model_id": source_model_id,
                        "army_id": army_id,
                    },
                ),
                DecisionOption.create(
                    "Set up in Reserves",
                    payload={
                        "choice_key": "RESERVES",
                        "source_unit_id": source_unit_id,
                        "source_model_id": source_model_id,
                        "army_id": army_id,
                    },
                ),
            ]
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Falsehood: choose whether the bearer starts on the battlefield or in Reserves.",
                player_id=getattr(owner, "id", None),
                options=options,
                context={
                    "ability": self._DECEPTORS_FALSEHOOD_DECLARE_ABILITY,
                    "ability_name": self._DECEPTORS_FALSEHOOD_SOURCE,
                    "phase": "Declare Battle Formations step",
                    "source_unit_id": source_unit_id,
                    "source_model_id": source_model_id,
                    "army_id": army_id,
                    "allowed_choice_keys": ["DEPLOY", "RESERVES"],
                    "optional": False,
                },
            )
            if hasattr(resolved_game, "request_decision"):
                resolved_game.request_decision(request)

    def select_deceptors_falsehood_declare_choice(
        self,
        source_unit_id: str,
        choice_key: str,
        *,
        game=None,
        player=None,
    ) -> dict:
        if not self.can_select_deceptors_falsehood_declare(source_unit_id, game=game, player=player):
            return {"ok": False, "reason": "Falsehood deployment choice is not available."}
        entry = self._deceptors_source_entry(source_unit_id, flag_key="enhancement_falsehood")
        if entry is None:
            return {"ok": False, "reason": "Falsehood source unit was not found."}
        root, member, sr, _bearer = entry
        key = str(choice_key or "").strip().upper()
        if key not in {"DEPLOY", "RESERVES"}:
            return {"ok": False, "reason": "Falsehood choice must be DEPLOY or RESERVES."}

        updated = dict(sr)
        updated["enhancement_falsehood_declare_resolved"] = True
        if key == "RESERVES":
            updated["enhancement_falsehood_in_reserves"] = True
            updated["enhancement_falsehood_reinforcements_available"] = True
            updated["enhancement_falsehood_reinforcements_used"] = False
            set_reserve_status = getattr(root, "set_reserve_status", None)
            if callable(set_reserve_status):
                set_reserve_status("reserves")
            else:
                root.reserve_status = "reserves"
            root.deployed = True
            root.arrived_from_reserves_this_turn = False
            game_map = getattr(game, "map", None) if game is not None else None
            units = getattr(game_map, "units", None)
            if isinstance(units, list) and root in units:
                units.remove(root)
        else:
            updated["enhancement_falsehood_in_reserves"] = False
            updated["enhancement_falsehood_reinforcements_available"] = False
            updated["enhancement_falsehood_reinforcements_used"] = False
        member.special_rules = updated
        self._clear_unit_ability_cache(member)
        self._clear_unit_ability_cache(root)
        return {
            "ok": True,
            "choice_key": key,
            "source_unit_id": str(get_entity_id(root) or ""),
            "source": self._DECEPTORS_FALSEHOOD_SOURCE,
        }

    def deceptors_falsehood_reinforcement_source_unit_ids(self, *, game=None, player=None) -> list[str]:
        if not self.is_deceptors() or self.army is None:
            return []
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return []
        out: list[str] = []
        for root, _member, sr, bearer in self._deceptors_sources_by_flag(flag_key="enhancement_falsehood"):
            if not self._model_alive(bearer):
                continue
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("enhancement_falsehood_in_reserves", False)):
                continue
            if not bool(sr.get("enhancement_falsehood_reinforcements_available", False)):
                continue
            if bool(sr.get("enhancement_falsehood_reinforcements_used", False)):
                continue
            in_reserves = getattr(root, "is_in_reserves", None)
            if callable(in_reserves) and not bool(in_reserves()):
                continue
            unit_id = str(get_entity_id(root) or "")
            if unit_id:
                out.append(unit_id)
        out.sort()
        return out

    def deceptors_falsehood_excludes_standard_reserves_arrival(self, unit, *, game=None, player=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        root_id = str(get_entity_id(root) or "")
        if not root_id:
            return False
        ids = set(self.deceptors_falsehood_reinforcement_source_unit_ids(game=game, player=player))
        return root_id in ids

    def deceptors_falsehood_candidate_models(self, source_unit_id: str, *, game=None, player=None) -> list[dict]:
        entry = self._deceptors_source_entry(source_unit_id, flag_key="enhancement_falsehood")
        if entry is None:
            return []
        source_root, _source_member, source_sr, _source_bearer = entry
        if not isinstance(source_sr, dict):
            return []
        if not bool(source_sr.get("enhancement_falsehood_reinforcements_available", False)):
            return []
        if bool(source_sr.get("enhancement_falsehood_reinforcements_used", False)):
            return []
        in_reserves = getattr(source_root, "is_in_reserves", None)
        if callable(in_reserves) and not bool(in_reserves()):
            return []

        candidates: list[dict] = []
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            if root is None or root is source_root:
                continue
            if not self._unit_in_army(root):
                continue
            if not self._unit_on_battlefield(root):
                continue
            if not (self._is_legionaries_unit(root) or self._is_chosen_unit(root)):
                continue
            if list(getattr(root, "attached_leaders", []) or []):
                continue
            alive_models = [m for m in list(getattr(root, "models", []) or []) if self._model_alive(m)]
            if len(alive_models) < 2:
                continue
            target_unit_id = str(get_entity_id(root) or "")
            if not target_unit_id:
                continue
            for model in alive_models:
                target_model_id = str(
                    get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or ""
                ).strip()
                if not target_model_id:
                    continue
                candidates.append(
                    {
                        "target_unit_id": target_unit_id,
                        "target_unit_name": str(getattr(root, "name", "Unit") or "Unit"),
                        "target_model_id": target_model_id,
                        "target_model_name": str(getattr(model, "name", "Model") or "Model"),
                    }
                )
        candidates.sort(key=lambda item: (str(item["target_unit_id"]), str(item["target_model_id"])))
        return candidates

    def queue_deceptors_falsehood_reinforcements_request(self, *, game=None, player=None) -> None:
        if not self.is_deceptors() or self.army is None:
            return
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None or not bool(getattr(resolved_game, "is_authoritative", True)):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        army_id = str(get_entity_id(self.army) or "")
        for source_unit_id in self.deceptors_falsehood_reinforcement_source_unit_ids(game=resolved_game, player=owner):
            if self._pending_deceptors_choose_quarry_request(
                resolved_game,
                ability=self._DECEPTORS_FALSEHOOD_REINFORCEMENTS_ABILITY,
                army_id=army_id,
                source_unit_id=source_unit_id,
            ):
                continue
            entry = self._deceptors_source_entry(source_unit_id, flag_key="enhancement_falsehood")
            if entry is None:
                continue
            _root, _member, _sr, bearer = entry
            source_model_id = str(get_entity_id(bearer) or getattr(bearer, "id", getattr(bearer, "_id", "")) or "")
            candidates = list(self.deceptors_falsehood_candidate_models(source_unit_id, game=resolved_game, player=owner) or [])
            if not candidates:
                continue
            options = [DecisionOption.create("None", payload={"action": "skip"})]
            for candidate in candidates:
                options.append(
                    DecisionOption.create(
                        f"{candidate['target_model_name']} ({candidate['target_unit_name']})",
                        payload={
                            "source_unit_id": source_unit_id,
                            "source_model_id": source_model_id,
                            "target_unit_id": candidate["target_unit_id"],
                            "target_model_id": candidate["target_model_id"],
                            "army_id": army_id,
                        },
                    )
                )
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Falsehood: select one model in a friendly Legionaries or Chosen unit (or None).",
                player_id=getattr(owner, "id", None),
                options=options,
                context={
                    "ability": self._DECEPTORS_FALSEHOOD_REINFORCEMENTS_ABILITY,
                    "ability_name": self._DECEPTORS_FALSEHOOD_SOURCE,
                    "phase": "Reinforcements step (Movement phase)",
                    "army_id": army_id,
                    "source_unit_id": source_unit_id,
                    "source_model_id": source_model_id,
                    "candidate_model_ids": [str(entry["target_model_id"]) for entry in candidates],
                    "optional": True,
                },
            )
            if hasattr(resolved_game, "request_decision"):
                resolved_game.request_decision(request)

    def select_deceptors_falsehood_reinforcements_target(
        self,
        source_unit_id: str,
        target_model_id: str,
        *,
        game=None,
        player=None,
    ) -> dict:
        entry = self._deceptors_source_entry(source_unit_id, flag_key="enhancement_falsehood")
        if entry is None:
            return {"ok": False, "reason": "Falsehood source unit was not found."}
        source_root, source_member, source_sr, source_bearer = entry
        if not isinstance(source_sr, dict):
            return {"ok": False, "reason": "Falsehood source state is unavailable."}
        if not bool(source_sr.get("enhancement_falsehood_reinforcements_available", False)):
            return {"ok": False, "reason": "Falsehood Reinforcements selection is unavailable."}
        if bool(source_sr.get("enhancement_falsehood_reinforcements_used", False)):
            return {"ok": False, "reason": "Falsehood has already been used."}

        target_id = str(target_model_id or "").strip()
        if not target_id:
            return {
                "ok": True,
                "skipped": True,
                "source_unit_id": str(get_entity_id(source_root) or ""),
                "source": self._DECEPTORS_FALSEHOOD_SOURCE,
            }

        candidate_by_model_id = {
            str(entry["target_model_id"]): entry
            for entry in list(self.deceptors_falsehood_candidate_models(source_unit_id, game=game, player=player) or [])
            if str(entry.get("target_model_id", "")).strip()
        }
        chosen = candidate_by_model_id.get(target_id)
        if chosen is None:
            return {"ok": False, "reason": "Falsehood selected model is ineligible."}
        target_model = self._deceptors_model_by_id(target_id)
        if target_model is None:
            return {"ok": False, "reason": "Falsehood target model was not found."}
        target_parent = getattr(target_model, "parent_unit", None)
        if target_parent is None:
            return {"ok": False, "reason": "Falsehood target model has no parent unit."}
        target_root = self._unit_root(target_parent)
        if target_root is None:
            return {"ok": False, "reason": "Falsehood target unit was not found."}
        can_attach = getattr(source_root, "can_attach_to", None)
        if callable(can_attach) and not bool(can_attach(target_root)):
            return {"ok": False, "reason": "Falsehood bearer cannot attach to the selected unit."}

        try:
            target_location = target_model.get_location()
        except Exception:
            return {"ok": False, "reason": "Falsehood target location is unavailable."}
        game_map = getattr(game, "map", None) if game is not None else None

        engaged_enemy_roots: list = []
        if game_map is not None and hasattr(game_map, "get_enemy_units"):
            from ..utility.aura_utils import model_within_engagement_range_of_unit

            enemy_units = list(game_map.get_enemy_units(target_root) or [])
            for enemy in enemy_units:
                enemy_root = self._unit_root(enemy)
                if enemy_root is None or not self._unit_on_battlefield(enemy_root):
                    continue
                if model_within_engagement_range_of_unit(target_model, enemy_root):
                    engaged_enemy_roots.append(enemy_root)

        placement = None
        if engaged_enemy_roots:
            placement = target_location
        else:
            find_pos = getattr(game, "_find_closest_valid_reposition_position", None) if game is not None else None
            if callable(find_pos):
                placement = find_pos(source_root, target_location, game_map=game_map)
            if not placement:
                placement = target_location
        if not placement:
            return {"ok": False, "reason": "Falsehood cannot set up the bearer near the selected model."}

        remove_model = getattr(target_parent, "remove_model", None)
        if not callable(remove_model):
            return {"ok": False, "reason": "Falsehood target model cannot be removed."}
        remove_model(target_model, fleed=True, game_map=game_map)

        try:
            facing = float(placement[3]) if len(placement) >= 4 else float(
                getattr(getattr(source_bearer, "model_base", None), "facing", 0.0) or 0.0
            )
        except Exception:
            facing = 0.0
        source_bearer.set_location(
            float(placement[0]),
            float(placement[1]),
            float(placement[2]),
            float(facing),
        )
        source_root.position = (float(placement[0]), float(placement[1]), float(placement[2]))
        if isinstance(getattr(game_map, "units", None), list) and source_root not in game_map.units:
            game_map.units.append(source_root)

        finalize = getattr(source_root, "_finalize_reserves_arrival", None)
        if callable(finalize):
            turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            finalize(turn=turn, game_map=game_map)
        else:
            source_root.deployed = True
            set_reserve_status = getattr(source_root, "set_reserve_status", None)
            if callable(set_reserve_status):
                set_reserve_status("deployed")
            else:
                source_root.reserve_status = "deployed"
            source_root.arrived_from_reserves_this_turn = True

        attach_to_unit = getattr(source_root, "attach_to_unit", None)
        if callable(attach_to_unit):
            try:
                attach_to_unit(target_root)
            except ValueError:
                return {"ok": False, "reason": "Falsehood bearer cannot attach to the selected unit."}

        updated = dict(source_sr)
        updated["enhancement_falsehood_in_reserves"] = False
        updated["enhancement_falsehood_reinforcements_available"] = False
        updated["enhancement_falsehood_reinforcements_used"] = True
        updated["enhancement_falsehood_selected_target_model_id"] = str(target_id)
        updated["enhancement_falsehood_selected_target_unit_id"] = str(get_entity_id(target_root) or "")
        source_member.special_rules = updated
        self._clear_unit_ability_cache(source_member)
        self._clear_unit_ability_cache(source_root)
        self._clear_unit_ability_cache(target_root)
        return {
            "ok": True,
            "source_unit_id": str(get_entity_id(source_root) or ""),
            "source_model_id": str(get_entity_id(source_bearer) or ""),
            "target_unit_id": str(get_entity_id(target_root) or ""),
            "target_model_id": str(target_id),
            "target_unit_name": str(getattr(target_root, "name", "Unit") or "Unit"),
            "target_model_name": str(getattr(target_model, "name", "Model") or "Model"),
            "source": self._DECEPTORS_FALSEHOOD_SOURCE,
        }

    def _clear_deceptors_soul_link_effect(self, member, sr: dict) -> bool:
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("enhancement_soul_link_active", False)):
            return False
        bearer = self._find_enhancement_bearer_on_member(member, sr)
        if self._model_alive(bearer) and bool(sr.get("enhancement_soul_link_added_psyker_keyword", False)):
            keywords = list(getattr(bearer, "keywords", []) or [])
            removed = False
            filtered: list[str] = []
            for keyword in keywords:
                if (not removed) and str(keyword or "").strip().upper() == "PSYKER":
                    removed = True
                    continue
                filtered.append(keyword)
            bearer.keywords = filtered
        updated = dict(sr)
        updated["enhancement_soul_link_active"] = False
        for key in (
            "enhancement_soul_link_target_model_id",
            "enhancement_soul_link_target_unit_id",
            "enhancement_soul_link_added_psyker_keyword",
            "enhancement_soul_link_turn",
            "enhancement_soul_link_turn_owner_id",
        ):
            updated.pop(key, None)
        member.special_rules = updated
        self._clear_unit_ability_cache(member)
        return True

    def expire_deceptors_soul_link_effects(self, *, game=None, player=None) -> None:
        if not self.is_deceptors() or self.army is None:
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        for root, member, sr, _bearer in self._deceptors_sources_by_flag(
            flag_key="enhancement_soul_link",
            require_alive_bearer=False,
        ):
            if self._clear_deceptors_soul_link_effect(member, sr):
                self._clear_unit_ability_cache(root)

    def can_select_deceptors_soul_link(self, *, game=None, player=None) -> bool:
        if not self.is_deceptors() or self.army is None:
            return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        army_player = getattr(self.army, "player", None)
        if army_player is not None and str(getattr(army_player, "id", "") or "") != str(getattr(owner, "id", "") or ""):
            return False
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return False
        phase_name = self._current_phase_name(game=resolved_game)
        if phase_name and phase_name != "COMMAND_PHASE":
            return False
        current_owner = str(self._current_turn_owner_id(game=resolved_game, player=owner) or "")
        if current_owner and current_owner != str(getattr(owner, "id", "") or ""):
            return False
        return True

    def deceptors_soul_link_candidate_models(self, source_unit_id: str, *, game=None, player=None) -> list[dict]:
        entry = self._deceptors_source_entry(source_unit_id, flag_key="enhancement_soul_link")
        if entry is None:
            return []
        source_root, _source_member, _source_sr, source_bearer = entry
        if source_root is None or self._unit_is_embarked(source_root):
            return []
        source_alive = getattr(source_root, "is_alive", None)
        if callable(source_alive) and not bool(source_alive()):
            return []
        source_bearer_id = str(get_entity_id(source_bearer) or getattr(source_bearer, "id", getattr(source_bearer, "_id", "")) or "")
        candidates: list[dict] = []
        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            if root is None:
                continue
            if self._unit_is_embarked(root):
                continue
            root_alive = getattr(root, "is_alive", None)
            if callable(root_alive) and not bool(root_alive()):
                continue
            get_members = getattr(root, "get_attached_unit_members", None)
            members = list(get_members() or []) if callable(get_members) else [root]
            if not members:
                members = [root]
            for member in members:
                if member is None:
                    continue
                for model in list(getattr(member, "models", []) or []):
                    if not self._model_alive(model):
                        continue
                    model_id = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "")
                    if not model_id or model_id == source_bearer_id:
                        continue
                    if not self._model_has_keyword(model, "INFANTRY"):
                        continue
                    if not self._model_has_keyword(model, "CHARACTER"):
                        continue
                    if not self._model_has_keyword(model, "HERETIC ASTARTES"):
                        continue
                    if self._model_has_keyword(model, "EPIC HERO"):
                        continue
                    candidates.append(
                        {
                            "target_unit_id": str(get_entity_id(root) or ""),
                            "target_unit_name": str(getattr(root, "name", "Unit") or "Unit"),
                            "target_model_id": model_id,
                            "target_model_name": str(getattr(model, "name", "Model") or "Model"),
                        }
                    )
        candidates.sort(key=lambda item: (str(item["target_unit_id"]), str(item["target_model_id"])))
        return candidates

    def queue_deceptors_soul_link_choice_request(self, *, game=None, player=None) -> None:
        if not self.is_deceptors() or self.army is None:
            return
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None or not bool(getattr(resolved_game, "is_authoritative", True)):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        if not self.can_select_deceptors_soul_link(game=resolved_game, player=owner):
            return
        self.expire_deceptors_soul_link_effects(game=resolved_game, player=owner)

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        army_id = str(get_entity_id(self.army) or "")
        for root, _member, _sr, bearer in self._deceptors_sources_by_flag(flag_key="enhancement_soul_link"):
            if root is None or self._unit_is_embarked(root):
                continue
            root_alive = getattr(root, "is_alive", None)
            if callable(root_alive) and not bool(root_alive()):
                continue
            source_unit_id = str(get_entity_id(root) or "")
            if not source_unit_id:
                continue
            if self._pending_deceptors_choose_quarry_request(
                resolved_game,
                ability=self._DECEPTORS_SOUL_LINK_ABILITY,
                army_id=army_id,
                source_unit_id=source_unit_id,
            ):
                continue
            source_model_id = str(get_entity_id(bearer) or getattr(bearer, "id", getattr(bearer, "_id", "")) or "")
            candidates = self.deceptors_soul_link_candidate_models(source_unit_id, game=resolved_game, player=owner)
            if not candidates:
                continue
            options = [DecisionOption.create("None", payload={"action": "skip"})]
            for candidate in candidates:
                options.append(
                    DecisionOption.create(
                        f"{candidate['target_model_name']} ({candidate['target_unit_name']})",
                        payload={
                            "source_unit_id": source_unit_id,
                            "source_model_id": source_model_id,
                            "target_unit_id": candidate["target_unit_id"],
                            "target_model_id": candidate["target_model_id"],
                            "army_id": army_id,
                        },
                    )
                )
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Soul Link: select one other friendly HERETIC ASTARTES INFANTRY CHARACTER model (or None).",
                player_id=getattr(owner, "id", None),
                options=options,
                context={
                    "ability": self._DECEPTORS_SOUL_LINK_ABILITY,
                    "ability_name": self._DECEPTORS_SOUL_LINK_SOURCE,
                    "phase": "Command phase",
                    "army_id": army_id,
                    "source_unit_id": source_unit_id,
                    "source_model_id": source_model_id,
                    "candidate_model_ids": [str(entry["target_model_id"]) for entry in candidates],
                    "optional": True,
                },
            )
            if hasattr(resolved_game, "request_decision"):
                resolved_game.request_decision(request)

    def select_deceptors_soul_link_target(
        self,
        source_unit_id: str,
        target_model_id: str,
        *,
        game=None,
        player=None,
    ) -> dict:
        if not self.can_select_deceptors_soul_link(game=game, player=player):
            return {"ok": False, "reason": "Soul Link target cannot be selected right now."}
        entry = self._deceptors_source_entry(source_unit_id, flag_key="enhancement_soul_link")
        if entry is None:
            return {"ok": False, "reason": "Soul Link source unit was not found."}
        source_root, source_member, source_sr, source_bearer = entry
        if not isinstance(source_sr, dict):
            return {"ok": False, "reason": "Soul Link source state is unavailable."}
        self._clear_deceptors_soul_link_effect(source_member, source_sr)
        source_sr = dict(getattr(source_member, "special_rules", {}) or {})

        target_id = str(target_model_id or "").strip()
        if not target_id:
            return {
                "ok": True,
                "skipped": True,
                "source_unit_id": str(get_entity_id(source_root) or ""),
                "source": self._DECEPTORS_SOUL_LINK_SOURCE,
            }

        candidate_by_model_id = {
            str(entry["target_model_id"]): entry
            for entry in list(self.deceptors_soul_link_candidate_models(source_unit_id, game=game, player=player) or [])
            if str(entry.get("target_model_id", "")).strip()
        }
        chosen = candidate_by_model_id.get(target_id)
        if chosen is None:
            return {"ok": False, "reason": "Soul Link selected model is ineligible."}
        target_model = self._deceptors_model_by_id(target_id)
        if target_model is None:
            return {"ok": False, "reason": "Soul Link target model was not found."}
        target_parent = getattr(target_model, "parent_unit", None)
        target_root = self._unit_root(target_parent)
        if target_root is None:
            return {"ok": False, "reason": "Soul Link target unit was not found."}

        added_psyker_keyword = False
        if not self._model_has_keyword(source_bearer, "PSYKER"):
            keywords = list(getattr(source_bearer, "keywords", []) or [])
            keywords.append("PSYKER")
            source_bearer.keywords = keywords
            added_psyker_keyword = True

        updated = dict(source_sr)
        updated["enhancement_soul_link_active"] = True
        updated["enhancement_soul_link_target_model_id"] = str(target_id)
        updated["enhancement_soul_link_target_unit_id"] = str(get_entity_id(target_root) or "")
        updated["enhancement_soul_link_added_psyker_keyword"] = bool(added_psyker_keyword)
        updated["enhancement_soul_link_turn"] = int(self._current_turn(game=game) or 0)
        updated["enhancement_soul_link_turn_owner_id"] = str(self._current_turn_owner_id(game=game, player=player) or "")
        source_member.special_rules = updated
        self._clear_unit_ability_cache(source_member)
        self._clear_unit_ability_cache(source_root)
        return {
            "ok": True,
            "source_unit_id": str(get_entity_id(source_root) or ""),
            "source_model_id": str(get_entity_id(source_bearer) or ""),
            "target_unit_id": str(get_entity_id(target_root) or ""),
            "target_model_id": str(target_id),
            "target_unit_name": str(getattr(target_root, "name", "Unit") or "Unit"),
            "target_model_name": str(getattr(target_model, "name", "Model") or "Model"),
            "added_psyker_keyword": bool(added_psyker_keyword),
            "source": self._DECEPTORS_SOUL_LINK_SOURCE,
        }

    def deceptors_soul_link_replacement_abilities(self, unit):
        if not self.is_deceptors() or self.army is None:
            return None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            if member is not unit:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("enhancement_soul_link_active", False)):
                continue
            target_unit_id = str(sr.get("enhancement_soul_link_target_unit_id", "") or "").strip()
            if not target_unit_id:
                return []
            target_root = self._deceptors_unit_by_id(target_unit_id)
            if target_root is None:
                return []
            return list(getattr(target_root, "possible_abilities", []) or [])
        return None

    @classmethod
    def _normalize_pactbound_mark(cls, value: str) -> str:
        mark = " ".join(str(value or "").strip().upper().replace("_", " ").split())
        if mark in {"UNDIVIDED", "UNIDIVIDED", "CHAOS UNDIVIDED"}:
            return "CHAOS UNDIVIDED"
        if mark in {"KHORNE", "TZEENTCH", "NURGLE", "SLAANESH"}:
            return mark
        return ""

    @classmethod
    def _pactbound_mark_display(cls, mark: str) -> str:
        norm = cls._normalize_pactbound_mark(mark)
        if norm == "CHAOS UNDIVIDED":
            return "Chaos Undivided"
        if norm:
            return norm.title()
        return str(mark or "").strip()

    def _unit_is_epic_hero(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return bool(self._unit_has_keyword(root, "EPIC HERO"))

    def _unit_is_psyker(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return bool(self._unit_has_keyword(root, "PSYKER"))

    def _pactbound_keyword_marks_for_unit(self, unit) -> list[str]:
        root = self._unit_root(unit)
        if root is None:
            return []
        marks: list[str] = []
        for mark in ("KHORNE", "TZEENTCH", "NURGLE", "SLAANESH"):
            if self._unit_has_keyword(root, mark):
                marks.append(mark)
        if (
            self._unit_has_keyword(root, "CHAOS UNDIVIDED")
            or self._unit_has_keyword(root, "UNDIVIDED")
            or self._unit_has_keyword(root, "UNIDIVIDED")
        ):
            marks.append("CHAOS UNDIVIDED")
        unique: list[str] = []
        for mark in marks:
            if mark not in unique:
                unique.append(mark)
        return unique

    def _set_pactbound_mark_for_unit(self, unit, mark: str) -> str:
        root = self._unit_root(unit)
        if root is None:
            return ""
        norm_mark = self._normalize_pactbound_mark(mark)
        if not norm_mark:
            return ""
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        updated = dict(sr)
        updated["pactbound_zealots_mark"] = norm_mark
        updated["pactbound_zealots_mark_source"] = self._PACTBOUND_MARK_SOURCE

        has_mark_keyword = bool(self._unit_has_keyword(root, norm_mark))
        if norm_mark == "CHAOS UNDIVIDED":
            has_mark_keyword = bool(
                has_mark_keyword
                or self._unit_has_keyword(root, "UNDIVIDED")
                or self._unit_has_keyword(root, "UNIDIVIDED")
            )
        if not has_mark_keyword:
            extra = list(updated.get("ability_added_keywords", []) or [])
            display_keyword = self._pactbound_mark_display(norm_mark)
            lowered = {str(k or "").strip().lower() for k in extra}
            if display_keyword.strip().lower() not in lowered:
                extra.append(display_keyword)
                updated["ability_added_keywords"] = extra

        root.special_rules = updated
        self._clear_unit_ability_cache(root)
        return norm_mark

    def ensure_pactbound_mark_for_unit(self, unit, *, assign_default: bool = True) -> str:
        if not self.is_pactbound_zealots() or self.army is None:
            return ""
        root = self._unit_root(unit)
        if root is None:
            return ""
        if not self._unit_in_army(root):
            return ""
        if not self._unit_is_heretic_astartes(root):
            return ""

        sr = getattr(root, "special_rules", None)
        stored_mark = self._normalize_pactbound_mark(str(sr.get("pactbound_zealots_mark", "") or "")) if isinstance(sr, dict) else ""
        keyword_marks = self._pactbound_keyword_marks_for_unit(root)
        if len(keyword_marks) > 1:
            return ""
        keyword_mark = keyword_marks[0] if keyword_marks else ""
        if stored_mark and keyword_mark and stored_mark != keyword_mark:
            return ""
        is_epic_hero = self._unit_is_epic_hero(root)
        selected_mark = stored_mark or keyword_mark
        if not selected_mark and (not is_epic_hero) and bool(assign_default):
            selected_mark = "CHAOS UNDIVIDED"
        if not selected_mark:
            return ""
        if selected_mark == "KHORNE" and self._unit_is_psyker(root):
            return ""
        if is_epic_hero:
            return selected_mark
        return self._set_pactbound_mark_for_unit(root, selected_mark)

    def pactbound_mark_for_unit(self, unit, *, assign_default: bool = True) -> str:
        return self.ensure_pactbound_mark_for_unit(unit, assign_default=assign_default)

    def _pactbound_dark_pact_state(self, attacker_model) -> tuple[str, bool]:
        unit = self._unit_root(getattr(attacker_model, "parent_unit", None)) if attacker_model is not None else None
        if unit is None:
            return "", False
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("dark_pacts_active", False)):
            return "", False
        choice = str(sr.get("dark_pacts_choice", "") or "").strip().upper()
        if not choice:
            return "", False
        passed = bool(sr.get("dark_pacts_test_passed", True))
        return choice, passed

    def pactbound_zealots_eye_of_tzeentch_on_dark_pact(self, unit, *, game=None) -> dict:
        if not self.is_pactbound_zealots() or self.army is None:
            return {}
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return {}
        member, source_sr, bearer = self._pactbound_zealots_enhancement_source_member(
            root,
            flag_key="enhancement_eye_of_tzeentch",
            require_bearer_alive=True,
            require_bearer_on_battlefield=True,
        )
        if member is None or not isinstance(source_sr, dict):
            return {}
        root_sr = getattr(root, "special_rules", None)
        if not isinstance(root_sr, dict) or not bool(root_sr.get("dark_pacts_active", False)):
            return {}
        if bool(source_sr.get("enhancement_eye_of_tzeentch_requires_dark_pact_passed", True)) and not bool(
            root_sr.get("dark_pacts_test_passed", False)
        ):
            return {}
        try:
            modified_roll = int(getattr(root, "_last_leadership_test_modified_roll", 0) or 0)
        except (TypeError, ValueError):
            modified_roll = 0
        try:
            threshold = int(source_sr.get("enhancement_eye_of_tzeentch_modified_roll_threshold", 8) or 8)
        except (TypeError, ValueError):
            threshold = 8
        threshold = min(12, max(2, threshold))
        source = (
            str(source_sr.get("enhancement_eye_of_tzeentch_source", "") or self._PACTBOUND_EYE_OF_TZEENTCH_SOURCE).strip()
            or self._PACTBOUND_EYE_OF_TZEENTCH_SOURCE
        )
        if modified_roll < threshold:
            return {
                "triggered": False,
                "source": source,
                "modified_roll": int(modified_roll),
                "modified_roll_threshold": int(threshold),
                "gained": 0,
            }
        owner = getattr(self.army, "player", None)
        gain_cp = getattr(owner, "gain_command_points", None) if owner is not None else None
        if not callable(gain_cp):
            return {}
        try:
            cp_gain = int(source_sr.get("enhancement_eye_of_tzeentch_cp_gain", 1) or 1)
        except (TypeError, ValueError):
            cp_gain = 1
        cp_gain = max(1, cp_gain)
        try:
            gained = int(gain_cp(cp_gain, reason=source) or 0)
        except (TypeError, ValueError):
            gained = 0
        return {
            "triggered": True,
            "source": source,
            "modified_roll": int(modified_roll),
            "modified_roll_threshold": int(threshold),
            "cp_gain": int(cp_gain),
            "gained": int(gained),
            "source_unit_id": str(get_entity_id(root) or ""),
            "source_model_id": str(get_entity_id(bearer) or "") if bearer is not None else "",
            "phase": str(self._current_phase_name(game=game) or ""),
        }

    def set_pactbound_zealots_talisman_of_burning_blood_dark_pact_bonus(
        self,
        unit,
        *,
        dark_pact_passed: bool,
        phase_name: str = "",
        game=None,
        player=None,
    ) -> dict:
        if not self.is_pactbound_zealots():
            return {}
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return {}
        member, source_sr, bearer = self._pactbound_zealots_enhancement_source_member(
            root,
            flag_key="enhancement_talisman_of_burning_blood",
            require_bearer_alive=True,
            require_bearer_on_battlefield=False,
        )
        if member is None or not isinstance(source_sr, dict):
            return {}
        updated = dict(source_sr)
        for key in (
            self._PACTBOUND_TALISMAN_DARK_PACT_BONUS_KEY,
            self._PACTBOUND_TALISMAN_DARK_PACT_EXPIRES_PHASE_KEY,
            self._PACTBOUND_TALISMAN_DARK_PACT_TURN_KEY,
            self._PACTBOUND_TALISMAN_DARK_PACT_OWNER_KEY,
        ):
            updated.pop(key, None)
        if not bool(dark_pact_passed):
            member.special_rules = updated
            return {"triggered": False, "source": "", "bonus": 0}
        if bool(updated.get("enhancement_talisman_of_burning_blood_requires_dark_pact_passed", True)) and not bool(
            dark_pact_passed
        ):
            member.special_rules = updated
            return {"triggered": False, "source": "", "bonus": 0}
        roll_spec = str(updated.get("enhancement_talisman_of_burning_blood_dark_pact_roll", "D3") or "D3").strip().upper()
        if not roll_spec:
            roll_spec = "D3"
        try:
            rolled_bonus = int(get_roll(roll_spec) or 0)
        except (TypeError, ValueError):
            rolled_bonus = 0
        if rolled_bonus <= 0:
            rolled_bonus = 1
        phase_key = str(phase_name or "").strip().upper() or self._current_phase_name(game=game)
        updated[self._PACTBOUND_TALISMAN_DARK_PACT_BONUS_KEY] = int(rolled_bonus)
        updated[self._PACTBOUND_TALISMAN_DARK_PACT_EXPIRES_PHASE_KEY] = str(phase_key or "")
        updated[self._PACTBOUND_TALISMAN_DARK_PACT_TURN_KEY] = int(self._current_turn(game=game) or 0)
        updated[self._PACTBOUND_TALISMAN_DARK_PACT_OWNER_KEY] = str(
            self._current_turn_owner_id(game=game, player=player) or ""
        ).strip()
        member.special_rules = updated
        source = str(
            updated.get("enhancement_talisman_of_burning_blood_source", "") or self._PACTBOUND_TALISMAN_OF_BURNING_BLOOD_SOURCE
        ).strip() or self._PACTBOUND_TALISMAN_OF_BURNING_BLOOD_SOURCE
        return {
            "triggered": True,
            "source": source,
            "bonus": int(rolled_bonus),
            "source_unit_id": str(get_entity_id(root) or ""),
            "source_model_id": str(get_entity_id(bearer) or "") if bearer is not None else "",
            "phase": str(phase_key or ""),
        }

    def _pactbound_zealots_talisman_dark_pact_window_active(self, source_sr: dict, *, game=None) -> bool:
        expected_phase = str(source_sr.get(self._PACTBOUND_TALISMAN_DARK_PACT_EXPIRES_PHASE_KEY, "") or "").strip().upper()
        current_phase = self._current_phase_name(game=game)
        if expected_phase and current_phase and expected_phase != current_phase:
            return False
        expected_owner = str(source_sr.get(self._PACTBOUND_TALISMAN_DARK_PACT_OWNER_KEY, "") or "").strip()
        current_owner = self._current_turn_owner_id(game=game)
        if expected_owner and current_owner and expected_owner != current_owner:
            return False
        try:
            expected_turn = int(source_sr.get(self._PACTBOUND_TALISMAN_DARK_PACT_TURN_KEY, 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0
        current_turn = self._current_turn(game=game)
        if expected_turn and current_turn and expected_turn != current_turn:
            return False
        return True

    def pactbound_zealots_talisman_of_burning_blood_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, int, str]:
        if not self.is_pactbound_zealots():
            return 0, 0, ""
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, 0, ""
        if not self._model_is_heretic_astartes(attacker_model):
            return 0, 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee = getattr(parent, "is_melee", None) if parent is not None else None
            if callable(is_melee) and not bool(is_melee()):
                return 0, 0, ""
        root = self._unit_root(getattr(attacker_model, "parent_unit", None))
        if root is None:
            return 0, 0, ""
        member, source_sr, bearer = self._pactbound_zealots_enhancement_source_member(
            root,
            flag_key="enhancement_talisman_of_burning_blood",
            require_bearer_alive=True,
            require_bearer_on_battlefield=False,
        )
        if member is None or not isinstance(source_sr, dict):
            return 0, 0, ""
        if not self._model_matches_bearer(attacker_model, bearer):
            return 0, 0, ""
        try:
            base_attacks_bonus = int(source_sr.get("enhancement_talisman_of_burning_blood_base_attacks_bonus", 1) or 1)
        except (TypeError, ValueError):
            base_attacks_bonus = 1
        try:
            base_strength_bonus = int(source_sr.get("enhancement_talisman_of_burning_blood_base_strength_bonus", 1) or 1)
        except (TypeError, ValueError):
            base_strength_bonus = 1
        base_attacks_bonus = max(0, base_attacks_bonus)
        base_strength_bonus = max(0, base_strength_bonus)
        try:
            dark_pact_bonus = int(source_sr.get(self._PACTBOUND_TALISMAN_DARK_PACT_BONUS_KEY, 0) or 0)
        except (TypeError, ValueError):
            dark_pact_bonus = 0
        if dark_pact_bonus > 0 and self._pactbound_zealots_talisman_dark_pact_window_active(source_sr, game=game):
            base_attacks_bonus = int(dark_pact_bonus)
            base_strength_bonus = int(dark_pact_bonus)
        source = str(
            source_sr.get("enhancement_talisman_of_burning_blood_source", "") or self._PACTBOUND_TALISMAN_OF_BURNING_BLOOD_SOURCE
        ).strip() or self._PACTBOUND_TALISMAN_OF_BURNING_BLOOD_SOURCE
        return int(base_attacks_bonus), int(base_strength_bonus), source

    def pactbound_zealots_crit_hit_threshold(self, attacker_model, *, weapon_profile=None) -> tuple[int, str]:
        if not self.is_pactbound_zealots():
            return 0, ""
        if attacker_model is None or not self._model_in_army(attacker_model):
            return 0, ""
        if not self._model_is_heretic_astartes(attacker_model):
            return 0, ""
        dark_pact_choice, passed = self._pactbound_dark_pact_state(attacker_model)
        if not dark_pact_choice or not passed:
            return 0, ""

        mark = self.ensure_pactbound_mark_for_unit(getattr(attacker_model, "parent_unit", None), assign_default=True)
        if mark not in self._PACTBOUND_MARKS:
            return 0, ""
        parent = getattr(weapon_profile, "parent_wargear", None) if weapon_profile is not None else None
        is_melee = bool(getattr(parent, "is_melee", lambda: False)())
        is_ranged = bool(getattr(parent, "is_ranged", lambda: False)())

        if dark_pact_choice in {"LETHAL HITS", "BOTH"}:
            if mark == "KHORNE" and is_melee:
                return 5, f"{self._PACTBOUND_MARK_SOURCE} ({self._pactbound_mark_display(mark)})"
            if mark == "TZEENTCH" and is_ranged:
                return 5, f"{self._PACTBOUND_MARK_SOURCE} ({self._pactbound_mark_display(mark)})"
        if dark_pact_choice == "BOTH" or dark_pact_choice.startswith("SUSTAINED"):
            if mark == "NURGLE" and is_ranged:
                return 5, f"{self._PACTBOUND_MARK_SOURCE} ({self._pactbound_mark_display(mark)})"
            if mark == "SLAANESH" and is_melee:
                return 5, f"{self._PACTBOUND_MARK_SOURCE} ({self._pactbound_mark_display(mark)})"
        return 0, ""

    def pactbound_zealots_reroll_hit_ones(self, attacker_model, *, weapon_profile=None) -> tuple[bool, str]:
        if not self.is_pactbound_zealots():
            return False, ""
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        if not self._model_is_heretic_astartes(attacker_model):
            return False, ""
        dark_pact_choice, passed = self._pactbound_dark_pact_state(attacker_model)
        if not dark_pact_choice or not passed:
            return False, ""
        mark = self.ensure_pactbound_mark_for_unit(getattr(attacker_model, "parent_unit", None), assign_default=True)
        if mark != "CHAOS UNDIVIDED":
            return False, ""
        if dark_pact_choice == "BOTH" or dark_pact_choice == "LETHAL HITS" or dark_pact_choice.startswith("SUSTAINED"):
            return True, f"{self._PACTBOUND_MARK_SOURCE} ({self._pactbound_mark_display(mark)})"
        return False, ""

    @staticmethod
    def _pactbound_effect_source(sr: dict, *, prefix: str, default: str) -> str:
        return str(sr.get(f"{prefix}_source", "") or default).strip() or default

    def pactbound_profane_zeal_reroll_wound_applies(
        self,
        attacker_model,
        *,
        target_unit=None,
        attack_type: str = "any",
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        _ = target_unit
        _ = attack_type
        _ = weapon_profile
        if attacker_model is None or not self._model_in_army(attacker_model):
            return False, ""
        root, sr = self._pactbound_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._PACTBOUND_PROFANE_ZEAL_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        if self.pactbound_mark_for_unit(root, assign_default=True) != "CHAOS UNDIVIDED":
            return False, ""
        return True, self._pactbound_effect_source(
            sr,
            prefix=self._PACTBOUND_PROFANE_ZEAL_PREFIX,
            default=self._PACTBOUND_PROFANE_ZEAL_SOURCE,
        )

    def pactbound_torpefying_refrain_can_shoot_after_fall_back(self, unit, profile=None, *, game=None) -> bool:
        if profile is not None and not self._weapon_profile_matches_attack_type(profile, "ranged"):
            return False
        root, _sr = self._pactbound_effect_state(
            unit,
            prefix=self._PACTBOUND_TORPEFYING_REFRAIN_PREFIX,
            game=game,
            require_phase_match=False,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False
        return bool(self.pactbound_mark_for_unit(root, assign_default=True) == "SLAANESH")

    def pactbound_torpefying_refrain_can_charge_after_fall_back(self, unit, *, game=None) -> bool:
        root, _sr = self._pactbound_effect_state(
            unit,
            prefix=self._PACTBOUND_TORPEFYING_REFRAIN_PREFIX,
            game=game,
            require_phase_match=False,
        )
        return bool(root is not None and self._unit_is_heretic_astartes(root))

    def pactbound_torpefying_refrain_can_charge_after_advance(self, unit, *, game=None) -> bool:
        root, _sr = self._pactbound_effect_state(
            unit,
            prefix=self._PACTBOUND_TORPEFYING_REFRAIN_PREFIX,
            game=game,
            require_phase_match=False,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False
        return bool(self.pactbound_mark_for_unit(root, assign_default=True) == "SLAANESH")

    def pactbound_eternal_hate_fight_on_death_rule(self, unit, *, model=None, game=None) -> Optional[dict]:
        _ = model
        root, sr = self._pactbound_effect_state(
            unit,
            prefix=self._PACTBOUND_ETERNAL_HATE_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return None
        threshold = 4
        if self.pactbound_mark_for_unit(root, assign_default=True) == "KHORNE":
            threshold = 3
        return {
            "threshold": int(max(2, min(6, threshold))),
            "source": self._pactbound_effect_source(
                sr,
                prefix=self._PACTBOUND_ETERNAL_HATE_PREFIX,
                default=self._PACTBOUND_ETERNAL_HATE_SOURCE,
            ),
        }

    def pactbound_eye_of_the_gods_candidate_models(self, unit) -> list:
        if not self.is_pactbound_zealots() or self.army is None:
            return []
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return []
        if not self._unit_is_heretic_astartes(root):
            return []
        members_fn = getattr(root, "get_attached_unit_members", None)
        members = list(members_fn() or []) if callable(members_fn) else [root]
        if not members:
            members = [root]
        for member in members:
            if member is None:
                continue
            if self._unit_has_keyword(member, "DAMNED"):
                return []
            if self._unit_has_keyword(member, "DAEMON"):
                return []
            if self._unit_has_keyword(member, "EPIC HERO"):
                return []
        models_fn = getattr(root, "get_attached_unit_models", None)
        models = list(models_fn() or []) if callable(models_fn) else list(getattr(root, "models", []) or [])
        candidates: list = []
        for model in list(models or []):
            if model is None or not self._model_alive(model):
                continue
            if not self._model_is_character_for_creations(model):
                continue
            candidates.append(model)
        return sorted(candidates, key=self._character_model_id)

    def _pactbound_eye_of_the_gods_bonus_count(self, model) -> tuple[int, str]:
        if not self.is_pactbound_zealots() or model is None or not self._model_in_army(model):
            return 0, ""
        root = self._unit_root(getattr(model, "parent_unit", None))
        if root is None or not self._unit_in_army(root):
            return 0, ""
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return 0, ""
        bonuses = sr.get(self._PACTBOUND_EYE_OF_THE_GODS_MODEL_BONUS_KEY, {})
        if not isinstance(bonuses, dict):
            return 0, ""
        try:
            bonus = int(bonuses.get(self._character_model_id(model), 0) or 0)
        except (TypeError, ValueError):
            bonus = 0
        if bonus <= 0:
            return 0, ""
        source = str(sr.get("pactbound_eye_of_the_gods_source", "") or self._PACTBOUND_EYE_OF_THE_GODS_SOURCE).strip()
        return int(bonus), (source or self._PACTBOUND_EYE_OF_THE_GODS_SOURCE)

    def apply_pactbound_eye_of_the_gods_to_model(self, model, *, source: str = "") -> dict:
        if not self.is_pactbound_zealots():
            return {"ok": False, "reason": "Detachment is not Pactbound Zealots."}
        if model is None or not self._model_in_army(model):
            return {"ok": False, "reason": "Target model is not in this army."}
        if not self._model_is_character_for_creations(model):
            return {"ok": False, "reason": "Target model is not a CHARACTER model."}
        root = self._unit_root(getattr(model, "parent_unit", None))
        if root is None:
            return {"ok": False, "reason": "Target model is not attached to a unit."}
        if model not in self.pactbound_eye_of_the_gods_candidate_models(root):
            return {"ok": False, "reason": "Target model is not eligible for Eye of the Gods."}

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        updated = dict(sr)
        bonuses = dict(updated.get(self._PACTBOUND_EYE_OF_THE_GODS_MODEL_BONUS_KEY, {}) or {})
        model_id = self._character_model_id(model)
        current_bonus = 0
        try:
            current_bonus = int(bonuses.get(model_id, 0) or 0)
        except (TypeError, ValueError):
            current_bonus = 0
        bonuses[model_id] = int(current_bonus + 1)
        updated[self._PACTBOUND_EYE_OF_THE_GODS_MODEL_BONUS_KEY] = bonuses
        updated["pactbound_eye_of_the_gods_source"] = (
            str(source or self._PACTBOUND_EYE_OF_THE_GODS_SOURCE).strip() or self._PACTBOUND_EYE_OF_THE_GODS_SOURCE
        )

        try:
            model._base_movement = int(getattr(model, "_base_movement", 0) or 0) + 1
            model._movement = int(getattr(model, "_movement", 0) or 0) + 1
        except (TypeError, ValueError):
            return {"ok": False, "reason": "Failed to update Move characteristic."}
        try:
            model._base_toughness = int(getattr(model, "_base_toughness", 0) or 0) + 1
            model._toughness = int(getattr(model, "_toughness", 0) or 0) + 1
        except (TypeError, ValueError):
            return {"ok": False, "reason": "Failed to update Toughness characteristic."}
        try:
            model._base_wounds = int(getattr(model, "_base_wounds", 0) or 0) + 1
            model._wounds = int(getattr(model, "_wounds", 0) or 0) + 1
            base_unmod = getattr(model, "_base_wounds_unmodified", None)
            if base_unmod is not None:
                model._base_wounds_unmodified = int(base_unmod or 0) + 1
        except (TypeError, ValueError):
            return {"ok": False, "reason": "Failed to update Wounds characteristic."}

        root.special_rules = updated
        try:
            models_fn = getattr(root, "get_attached_unit_models", None)
            models = list(models_fn() or []) if callable(models_fn) else list(getattr(root, "models", []) or [])
            root.starting_total_wounds = sum(int(getattr(entry, "_base_wounds", 0) or 0) for entry in list(models or []))
        except (TypeError, ValueError):
            pass
        self._clear_unit_ability_cache(root)
        return {
            "ok": True,
            "unit_id": self._unit_entity_key(root),
            "model_id": model_id,
            "bonus_count": int(bonuses.get(model_id, 0) or 0),
            "source": str(updated.get("pactbound_eye_of_the_gods_source", "") or self._PACTBOUND_EYE_OF_THE_GODS_SOURCE),
        }

    def pactbound_eye_of_the_gods_melee_attacks_bonus(self, attacker_model, *, weapon_profile=None, game=None) -> tuple[int, str]:
        _ = game
        if not self._weapon_profile_matches_attack_type(weapon_profile, "melee"):
            return 0, ""
        return self._pactbound_eye_of_the_gods_bonus_count(attacker_model)

    def pactbound_eye_of_the_gods_melee_strength_bonus(self, attacker_model, *, weapon_profile=None, game=None) -> tuple[int, str]:
        _ = game
        if not self._weapon_profile_matches_attack_type(weapon_profile, "melee"):
            return 0, ""
        return self._pactbound_eye_of_the_gods_bonus_count(attacker_model)

    def pactbound_eye_of_the_gods_melee_damage_bonus(self, attacker_model, *, weapon_profile=None, game=None) -> tuple[int, str]:
        _ = game
        if not self._weapon_profile_matches_attack_type(weapon_profile, "melee"):
            return 0, ""
        return self._pactbound_eye_of_the_gods_bonus_count(attacker_model)

    def pactbound_zealots_leader_marks_match(self, leader, bodyguard) -> bool:
        if not self.is_pactbound_zealots():
            return True
        if leader is None or bodyguard is None:
            return False
        if not self._unit_is_heretic_astartes(leader) or not self._unit_is_heretic_astartes(bodyguard):
            return True
        leader_mark = self.ensure_pactbound_mark_for_unit(leader, assign_default=True)
        bodyguard_mark = self.ensure_pactbound_mark_for_unit(bodyguard, assign_default=True)
        if not leader_mark or not bodyguard_mark:
            return False
        if leader_mark == "KHORNE" and self._unit_is_psyker(leader):
            return False
        if bodyguard_mark == "KHORNE" and self._unit_is_psyker(bodyguard):
            return False
        return leader_mark == bodyguard_mark

    def pactbound_zealots_transport_marks_match(self, transport_unit, passenger_unit) -> bool:
        if not self.is_pactbound_zealots():
            return True
        if transport_unit is None or passenger_unit is None:
            return False
        if not self._unit_is_heretic_astartes(transport_unit) or not self._unit_is_heretic_astartes(passenger_unit):
            return True
        transport_mark = self.ensure_pactbound_mark_for_unit(transport_unit, assign_default=True)
        passenger_mark = self.ensure_pactbound_mark_for_unit(passenger_unit, assign_default=True)
        if not transport_mark or not passenger_mark:
            return False
        if transport_mark == "KHORNE" and self._unit_is_psyker(transport_unit):
            return False
        if passenger_mark == "KHORNE" and self._unit_is_psyker(passenger_unit):
            return False
        return transport_mark == passenger_mark

    def _validate_pactbound_zealots_rules(self) -> list[str]:
        if not self.is_pactbound_zealots() or self.army is None:
            return []
        errors: list[str] = []

        for root in self._iter_unique_roots(getattr(self.army, "units", []) or []):
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_heretic_astartes(root):
                continue
            if self._unit_is_epic_hero(root):
                continue
            sr = getattr(root, "special_rules", None)
            raw_sr_mark = str(sr.get("pactbound_zealots_mark", "") or "").strip() if isinstance(sr, dict) else ""
            sr_mark = self._normalize_pactbound_mark(raw_sr_mark)
            keyword_marks = self._pactbound_keyword_marks_for_unit(root)
            if len(keyword_marks) > 1:
                errors.append(
                    f"Marks of Chaos: unit '{getattr(root, 'name', 'Unknown')}' has multiple mark keywords {keyword_marks}."
                )
                continue
            if raw_sr_mark and not sr_mark:
                errors.append(
                    f"Marks of Chaos: unit '{getattr(root, 'name', 'Unknown')}' has invalid mark '{raw_sr_mark}'."
                )
                continue
            keyword_mark = keyword_marks[0] if keyword_marks else ""
            if sr_mark and keyword_mark and sr_mark != keyword_mark:
                errors.append(
                    f"Marks of Chaos: unit '{getattr(root, 'name', 'Unknown')}' has conflicting marks '{sr_mark}' and '{keyword_mark}'."
                )
                continue
            selected_mark = sr_mark or keyword_mark or "CHAOS UNDIVIDED"
            if selected_mark == "KHORNE" and self._unit_is_psyker(root):
                errors.append(
                    f"Marks of Chaos restriction: PSYKER unit '{getattr(root, 'name', 'Unknown')}' cannot have the KHORNE keyword."
                )
                continue
            self._set_pactbound_mark_for_unit(root, selected_mark)

        for unit in list(getattr(self.army, "units", []) or []):
            attached_to = getattr(unit, "attached_to", None)
            if attached_to is None:
                continue
            if not self._unit_has_keyword(unit, "CHARACTER"):
                continue
            if not self._unit_is_heretic_astartes(unit) or not self._unit_is_heretic_astartes(attached_to):
                continue
            leader_mark = self.pactbound_mark_for_unit(unit, assign_default=False)
            bodyguard_mark = self.pactbound_mark_for_unit(attached_to, assign_default=False)
            if not leader_mark or not bodyguard_mark or leader_mark != bodyguard_mark:
                errors.append(
                    "Marks of Chaos restriction: a Character unit can only be attached to a unit if both share the same mark."
                )

        for transport in list(getattr(self.army, "units", []) or []):
            if not bool(getattr(transport, "is_transport", False)):
                continue
            if not self._unit_is_heretic_astartes(transport):
                continue
            passengers = list(getattr(transport, "transport_passengers", []) or [])
            for unit in list(getattr(self.army, "units", []) or []):
                if getattr(unit, "embarked_in", None) is transport and unit not in passengers:
                    passengers.append(unit)
            for passenger in passengers:
                if passenger is None:
                    continue
                if not self._unit_is_heretic_astartes(passenger):
                    continue
                transport_mark = self.pactbound_mark_for_unit(transport, assign_default=False)
                passenger_mark = self.pactbound_mark_for_unit(passenger, assign_default=False)
                if not transport_mark or not passenger_mark or transport_mark != passenger_mark:
                    errors.append(
                        "Marks of Chaos restriction: a unit can only embark in a TRANSPORT if both share the same mark."
                    )
        return errors

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        if self.is_chaos_cult():
            self.apply_chaos_cult_traitor_guardsmen_battleline_keywords()
        if self.is_cult_of_the_arkifane():
            self.apply_cult_of_the_arkifane_keywords()
        if self.is_pactbound_zealots():
            errors.extend(self._validate_pactbound_zealots_rules())
        return errors

    def slaves_to_none_disables_dark_pacts(self, unit=None) -> bool:
        if not self.is_renegade_warband():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        return bool(self._unit_is_heretic_astartes(root))

    def slaves_to_none_assault_applies(self, unit, weapon_profile=None) -> bool:
        if not self.is_renegade_warband():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_heretic_astartes(root):
            return False
        if weapon_profile is None:
            return True
        parent = getattr(weapon_profile, "parent_wargear", None)
        if parent is None:
            return False
        is_ranged = getattr(parent, "is_ranged", None)
        if callable(is_ranged):
            return bool(is_ranged())
        return False

    def raiders_and_reavers_assault_applies(self, unit, weapon_profile=None) -> bool:
        if not self.is_renegade_raiders():
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not self._unit_is_heretic_astartes(root):
            return False
        if weapon_profile is None:
            return True
        parent = getattr(weapon_profile, "parent_wargear", None)
        if parent is None:
            return False
        return bool(getattr(parent, "is_ranged", lambda: False)())

    def raiders_and_reavers_ap_bonus(self, model, target_unit, *, game_map=None) -> int:
        if not self.is_renegade_raiders():
            return 0
        if model is None or target_unit is None or not self._model_in_army(model):
            return 0
        if not self._model_is_heretic_astartes(model):
            return 0
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return 0
        within_objective = getattr(unit, "_target_within_objective_range", None)
        if not callable(within_objective):
            return 0
        if bool(within_objective(target_unit, game_map)):
            return 1
        return 0

    @staticmethod
    def _renegade_raiders_effect_source(sr: dict, *, prefix: str, default: str) -> str:
        return str(sr.get(f"{prefix}_source", "") or default).strip() or default

    def _renegade_raiders_target_within_objective_range(self, attacker_unit, target_unit, *, game=None) -> bool:
        root = self._unit_root(attacker_unit)
        target_root = self._unit_root(target_unit)
        if root is None or target_root is None:
            return False
        within_objective = getattr(root, "_target_within_objective_range", None)
        if not callable(within_objective):
            return False
        resolved_game = self._resolve_game(game=game)
        game_map = getattr(resolved_game, "map", None) if resolved_game is not None else None
        try:
            return bool(within_objective(target_root, game_map))
        except (AttributeError, TypeError, ValueError):
            return False

    def renegade_raiders_reavers_haste_can_charge_after_advance(self, unit, *, game=None) -> bool:
        root, _sr = self._renegade_raiders_effect_state(
            unit,
            prefix=self._RENEGADE_RAIDERS_REAVERS_HASTE_PREFIX,
            game=game,
            require_phase_match=False,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False
        return bool(self._unit_has_keyword(root, "INFANTRY") or self._unit_has_keyword(root, "MOUNTED"))

    def renegade_raiders_reavers_haste_charge_roll_bonus(self, unit, *, target_units=None, game=None) -> tuple[int, str]:
        root, sr = self._renegade_raiders_effect_state(
            unit,
            prefix=self._RENEGADE_RAIDERS_REAVERS_HASTE_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return 0, ""
        if not (self._unit_has_keyword(root, "INFANTRY") or self._unit_has_keyword(root, "MOUNTED")):
            return 0, ""
        targets = list(target_units or [])
        if not targets:
            return 0, ""
        if not any(self._renegade_raiders_target_within_objective_range(root, target, game=game) for target in targets):
            return 0, ""
        try:
            bonus = int(sr.get(f"{self._RENEGADE_RAIDERS_REAVERS_HASTE_PREFIX}_charge_roll_bonus", 1) or 0)
        except (TypeError, ValueError):
            bonus = 1
        if bonus <= 0:
            return 0, ""
        return int(bonus), self._renegade_raiders_effect_source(
            sr,
            prefix=self._RENEGADE_RAIDERS_REAVERS_HASTE_PREFIX,
            default=self._RENEGADE_RAIDERS_REAVERS_HASTE_SOURCE,
        )

    def renegade_raiders_ruinous_raid_reroll_hit_applies(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        _ = weapon_profile
        if attacker_model is None or target_unit is None or not self._model_in_army(attacker_model):
            return False, ""
        root, sr = self._renegade_raiders_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._RENEGADE_RAIDERS_RUINOUS_RAID_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        if not self._renegade_raiders_target_within_objective_range(root, target_unit, game=game):
            return False, ""
        return True, self._renegade_raiders_effect_source(
            sr,
            prefix=self._RENEGADE_RAIDERS_RUINOUS_RAID_PREFIX,
            default=self._RENEGADE_RAIDERS_RUINOUS_RAID_SOURCE,
        )

    def renegade_raiders_ruinous_raid_reroll_wound_applies(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        _ = weapon_profile
        if attacker_model is None or target_unit is None or not self._model_in_army(attacker_model):
            return False, ""
        root, sr = self._renegade_raiders_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._RENEGADE_RAIDERS_RUINOUS_RAID_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        if not self._renegade_raiders_target_within_objective_range(root, target_unit, game=game):
            return False, ""
        return True, self._renegade_raiders_effect_source(
            sr,
            prefix=self._RENEGADE_RAIDERS_RUINOUS_RAID_PREFIX,
            default=self._RENEGADE_RAIDERS_RUINOUS_RAID_SOURCE,
        )

    def renegade_raiders_scour_and_seize_precision_applies(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        if attacker_model is None or target_unit is None or not self._model_in_army(attacker_model):
            return False, ""
        if not self._weapon_profile_matches_attack_type(weapon_profile, "melee"):
            return False, ""
        root, sr = self._renegade_raiders_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix=self._RENEGADE_RAIDERS_SCOUR_AND_SEIZE_PREFIX,
            game=game,
        )
        if root is None or not self._unit_is_heretic_astartes(root):
            return False, ""
        if not self._renegade_raiders_target_within_objective_range(root, target_unit, game=game):
            return False, ""
        return True, self._renegade_raiders_effect_source(
            sr,
            prefix=self._RENEGADE_RAIDERS_SCOUR_AND_SEIZE_PREFIX,
            default=self._RENEGADE_RAIDERS_SCOUR_AND_SEIZE_SOURCE,
        )

    def _renegade_raiders_enhancement_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_on_battlefield: bool = False,
    ):
        if not self.is_renegade_raiders():
            return None, None, None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None, None, None
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
                continue
            bearer = self._find_enhancement_bearer_on_member(member, sr)
            if require_bearer_alive and not self._model_alive(bearer):
                continue
            if require_bearer_on_battlefield:
                bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None))
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue
            return root, member, sr, bearer
        return None, None, None, None

    @staticmethod
    def _model_base_radius(model) -> float:
        if model is None:
            return 0.0
        base = getattr(model, "model_base", None)
        if base is None:
            return 0.0
        radius = getattr(base, "radius", 0.0)
        get_radius = getattr(base, "get_radius", None)
        if callable(get_radius):
            radius = get_radius()
        if isinstance(radius, (tuple, list)):
            values = [float(v) for v in list(radius) if v is not None]
            if not values:
                return 0.0
            return max(0.0, float(max(values)))
        try:
            return max(0.0, float(radius))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _distance_to_rect_zone(x: float, y: float, zone) -> float | None:
        if not all(hasattr(zone, attr) for attr in ("x_min", "x_max", "y_min", "y_max")):
            return None
        try:
            x_min = float(getattr(zone, "x_min"))
            x_max = float(getattr(zone, "x_max"))
            y_min = float(getattr(zone, "y_min"))
            y_max = float(getattr(zone, "y_max"))
            px = float(x)
            py = float(y)
        except (TypeError, ValueError):
            return None
        dx = 0.0
        if px < x_min:
            dx = x_min - px
        elif px > x_max:
            dx = px - x_max
        dy = 0.0
        if py < y_min:
            dy = y_min - py
        elif py > y_max:
            dy = py - y_max
        return float((dx * dx + dy * dy) ** 0.5)

    def _enemy_deployment_zone_distance_for_point(
        self,
        *,
        game,
        owner_player_id: str,
        x: float,
        y: float,
    ) -> float:
        distance_fn = getattr(game, "get_distance_to_enemy_deployment_zone", None) if game is not None else None
        if callable(distance_fn):
            try:
                distance = float(distance_fn(float(x), float(y), str(owner_player_id)) or 0.0)
                if distance >= 0.0:
                    return distance
            except (TypeError, ValueError, AttributeError, RuntimeError):
                pass

        deployment_zones = dict(getattr(game, "deployment_zones", {}) or {}) if game is not None else {}
        min_distance = float("inf")
        for zone_player_id, zone in deployment_zones.items():
            if str(zone_player_id) == str(owner_player_id):
                continue
            mission_zones = list(dict(zone or {}).get("mission_zones", []) or [])
            for mission_zone in mission_zones:
                contains_point = getattr(mission_zone, "contains_point", None)
                if callable(contains_point):
                    try:
                        if bool(contains_point(float(x), float(y))):
                            return 0.0
                    except (TypeError, ValueError):
                        pass

                rect_distance = self._distance_to_rect_zone(float(x), float(y), mission_zone)
                if rect_distance is not None:
                    min_distance = min(min_distance, float(rect_distance))
                    continue

                vertices = getattr(mission_zone, "vertices", None)
                if not vertices:
                    continue
                try:
                    from shapely.geometry import Point as ShapelyPoint, Polygon as ShapelyPolygon
                except ImportError:
                    continue
                try:
                    polygon = ShapelyPolygon(vertices)
                    if not bool(getattr(polygon, "is_valid", True)):
                        polygon = polygon.buffer(0)
                    distance = float(ShapelyPoint(float(x), float(y)).distance(polygon))
                except (TypeError, ValueError):
                    continue
                if distance < min_distance:
                    min_distance = float(distance)
        return float(min_distance)

    def _model_wholly_within_enemy_deployment_zone_distance(
        self,
        model,
        *,
        game=None,
        distance_in: float,
    ) -> bool:
        if model is None or not self._model_alive(model):
            return False
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return False
        owner = getattr(self.army, "player", None) if self.army is not None else None
        owner_id = str(getattr(owner, "id", "") or "").strip()
        if not owner_id:
            return False
        get_location = getattr(model, "get_location", None)
        if not callable(get_location):
            return False
        try:
            x, y = get_location()[:2]
            x = float(x)
            y = float(y)
            max_distance = float(distance_in)
        except (TypeError, ValueError):
            return False
        if max_distance < 0.0:
            return False
        center_distance = self._enemy_deployment_zone_distance_for_point(
            game=resolved_game,
            owner_player_id=owner_id,
            x=x,
            y=y,
        )
        if center_distance == float("inf"):
            return False
        radius = self._model_base_radius(model)
        return bool(float(center_distance + radius) <= float(max_distance) + 1e-6)

    def _renegade_raiders_dread_reaver_source_for_model(self, model, *, game=None):
        if not self.is_renegade_raiders():
            return None
        if model is None or not self._model_in_army(model):
            return None
        root = self._unit_root(getattr(model, "parent_unit", None))
        if root is None:
            return None
        _source_root, _source_member, source_sr, bearer = self._renegade_raiders_enhancement_source_member(
            root,
            flag_key="enhancement_dread_reaver",
            require_bearer_alive=False,
            require_bearer_on_battlefield=False,
        )
        if source_sr is None or bearer is None:
            return None
        if not self._model_matches_bearer(model, bearer):
            return None
        if bool(source_sr.get("enhancement_dread_reaver_requires_bearer_alive", True)):
            if not self._model_alive(bearer):
                return None
        if bool(source_sr.get("enhancement_dread_reaver_requires_bearer_on_battlefield", True)):
            bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None))
            if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                return None
        try:
            distance_in = float(source_sr.get("enhancement_dread_reaver_enemy_deployment_zone_distance_in", 12.0) or 12.0)
        except (TypeError, ValueError):
            distance_in = 12.0
        if distance_in > 0.0 and not self._model_wholly_within_enemy_deployment_zone_distance(
            bearer,
            game=game,
            distance_in=distance_in,
        ):
            return None
        return source_sr

    def renegade_raiders_dread_reaver_reroll_hit_applies(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        _ = game
        if not self.is_renegade_raiders():
            return False, ""
        parent = getattr(weapon_profile, "parent_wargear", None) if weapon_profile is not None else None
        is_melee = getattr(parent, "is_melee", None) if parent is not None else None
        if callable(is_melee) and not bool(is_melee()):
            return False, ""
        source_sr = self._renegade_raiders_dread_reaver_source_for_model(attacker_model, game=game)
        if source_sr is None:
            return False, ""
        if not bool(source_sr.get("enhancement_dread_reaver_reroll_hit", True)):
            return False, ""
        source = str(
            source_sr.get("enhancement_dread_reaver_source", "") or self._RENEGADE_RAIDERS_DREAD_REAVER_SOURCE
        ).strip() or self._RENEGADE_RAIDERS_DREAD_REAVER_SOURCE
        return True, source

    def renegade_raiders_dread_reaver_reroll_wound_applies(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[bool, str]:
        _ = game
        if not self.is_renegade_raiders():
            return False, ""
        parent = getattr(weapon_profile, "parent_wargear", None) if weapon_profile is not None else None
        is_melee = getattr(parent, "is_melee", None) if parent is not None else None
        if callable(is_melee) and not bool(is_melee()):
            return False, ""
        source_sr = self._renegade_raiders_dread_reaver_source_for_model(attacker_model, game=game)
        if source_sr is None:
            return False, ""
        if not bool(source_sr.get("enhancement_dread_reaver_reroll_wound", True)):
            return False, ""
        source = str(
            source_sr.get("enhancement_dread_reaver_source", "") or self._RENEGADE_RAIDERS_DREAD_REAVER_SOURCE
        ).strip() or self._RENEGADE_RAIDERS_DREAD_REAVER_SOURCE
        return True, source

    def renegade_raiders_mark_of_the_hound_scout_distance(self, unit) -> float:
        if not self.is_renegade_raiders():
            return 0.0
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return 0.0
        _source_root, _source_member, source_sr, bearer = self._renegade_raiders_enhancement_source_member(
            root,
            flag_key="enhancement_mark_of_the_hound",
            require_bearer_alive=False,
            require_bearer_on_battlefield=False,
        )
        if source_sr is None or bearer is None:
            return 0.0
        if bool(source_sr.get("enhancement_mark_of_the_hound_requires_bearer_alive", True)):
            if not self._model_alive(bearer):
                return 0.0
        try:
            distance = float(source_sr.get("enhancement_mark_of_the_hound_scout_distance", 6.0) or 6.0)
        except (TypeError, ValueError):
            distance = 6.0
        return max(0.0, float(distance))

    def nightmare_hunt_sorrowscent_vulture_scout_distance(self, unit) -> float:
        if not self.is_nightmare_hunt():
            return 0.0
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return 0.0
        _source_member, source_sr, bearer = self._nightmare_hunt_enhancement_source_member(
            root,
            flag_key="enhancement_sorrowscent_vulture",
            require_bearer_alive=False,
            require_bearer_on_battlefield=False,
        )
        if source_sr is None or bearer is None:
            return 0.0
        if bool(source_sr.get("enhancement_sorrowscent_vulture_requires_bearer_alive", True)):
            if not self._model_alive(bearer):
                return 0.0
        try:
            distance = float(source_sr.get("enhancement_sorrowscent_vulture_scout_distance", 6.0) or 6.0)
        except (TypeError, ValueError):
            distance = 6.0
        return max(0.0, float(distance))

    def _renegade_raiders_tyrants_lash_source(self, unit):
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None
        _source_root, _source_member, source_sr, bearer = self._renegade_raiders_enhancement_source_member(
            root,
            flag_key="enhancement_tyrants_lash",
            require_bearer_alive=False,
            require_bearer_on_battlefield=False,
        )
        if source_sr is None or bearer is None:
            return None
        if bool(source_sr.get("enhancement_tyrants_lash_requires_bearer_alive", True)):
            if not self._model_alive(bearer):
                return None
        if bool(source_sr.get("enhancement_tyrants_lash_requires_bearer_on_battlefield", True)):
            bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None))
            if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                return None
        return source_sr

    def renegade_raiders_tyrants_lash_reroll_advance_applies(self, unit, *, game=None) -> bool:
        _ = game
        if not self.is_renegade_raiders():
            return False
        source_sr = self._renegade_raiders_tyrants_lash_source(unit)
        if source_sr is None:
            return False
        return bool(source_sr.get("enhancement_tyrants_lash_reroll_advance", True))

    def renegade_raiders_tyrants_lash_can_shoot_after_fall_back(self, unit, profile=None, *, game=None) -> bool:
        _ = game
        if not self.is_renegade_raiders():
            return False
        source_sr = self._renegade_raiders_tyrants_lash_source(unit)
        if source_sr is None:
            return False
        if not bool(source_sr.get("enhancement_tyrants_lash_allow_shoot_after_fall_back", True)):
            return False
        parent = getattr(profile, "parent_wargear", None) if profile is not None else None
        is_ranged = getattr(parent, "is_ranged", None) if parent is not None else None
        if callable(is_ranged):
            return bool(is_ranged())
        return True

    def renegade_raiders_despots_claim_on_command_phase_start(self, *, game=None) -> list[dict]:
        if not self.is_renegade_raiders() or self.army is None:
            return []
        owner = getattr(self.army, "player", None)
        gain_cp = getattr(owner, "gain_command_points", None) if owner is not None else None
        if not callable(gain_cp):
            return []

        roots = list(self._iter_unique_roots(getattr(self.army, "units", []) or []))
        roots.sort(key=lambda unit: str(get_entity_id(unit) or self._unit_root_key(unit)))

        out: list[dict] = []
        for root in roots:
            _source_root, _source_member, source_sr, bearer = self._renegade_raiders_enhancement_source_member(
                root,
                flag_key="enhancement_despots_claim",
                require_bearer_alive=True,
                require_bearer_on_battlefield=False,
            )
            if source_sr is None or bearer is None:
                continue
            if bool(source_sr.get("enhancement_despots_claim_requires_bearer_on_battlefield", True)):
                bearer_unit = self._unit_root(getattr(bearer, "parent_unit", None))
                if bearer_unit is None or not self._unit_on_battlefield(bearer_unit):
                    continue

            try:
                success_on = int(source_sr.get("enhancement_despots_claim_success_on", 5) or 5)
            except (TypeError, ValueError):
                success_on = 5
            success_on = int(min(6, max(2, success_on)))

            try:
                cp_gain = int(source_sr.get("enhancement_despots_claim_cp_gain", 1) or 1)
            except (TypeError, ValueError):
                cp_gain = 1
            cp_gain = int(max(1, cp_gain))

            try:
                zone_bonus = int(source_sr.get("enhancement_despots_claim_enemy_deployment_zone_bonus", 1) or 1)
            except (TypeError, ValueError):
                zone_bonus = 1
            zone_bonus = int(max(0, zone_bonus))

            try:
                zone_distance = float(
                    source_sr.get("enhancement_despots_claim_enemy_deployment_zone_distance_in", 12.0) or 12.0
                )
            except (TypeError, ValueError):
                zone_distance = 12.0
            zone_distance = max(0.0, float(zone_distance))

            source = str(
                source_sr.get("enhancement_despots_claim_source", "") or self._RENEGADE_RAIDERS_DESPOTS_CLAIM_SOURCE
            ).strip() or self._RENEGADE_RAIDERS_DESPOTS_CLAIM_SOURCE

            roll = int(get_roll("D6"))
            modifier = 0
            if zone_bonus > 0 and zone_distance > 0.0:
                if self._model_wholly_within_enemy_deployment_zone_distance(
                    bearer,
                    game=game,
                    distance_in=zone_distance,
                ):
                    modifier = int(zone_bonus)
            total = int(roll + modifier)
            gained = 0
            if total >= success_on:
                gained = int(gain_cp(cp_gain, reason=source) or 0)

            out.append(
                {
                    "triggered": True,
                    "source": source,
                    "roll": int(roll),
                    "roll_modifier": int(modifier),
                    "total": int(total),
                    "success_on": int(success_on),
                    "cp_gain": int(cp_gain),
                    "gained": int(gained),
                    "source_unit_id": str(get_entity_id(root) or ""),
                    "source_model_id": str(get_entity_id(bearer) or ""),
                }
            )
        return out
