from __future__ import annotations

import re

from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class GenestealerCultsDetachmentManager(DetachmentManagerBase):
    faction_id = "GC"

    _HYPERMORPHIC_FURY_RULE_NAME = "Hypermorphic Fury"
    _HYPERMORPHIC_FURY_ELIGIBLE_NAME_TOKENS = (
        "aberrants",
        "biophagus",
        "purestrain genestealers",
    )
    _BIO_HORROR_REVELATION_RULE_NAME = "Bio-Horror Revelation"
    _BIO_HORROR_ACTIVE_KEY = "gsc_bio_horror_revelation_active"
    _BIO_HORROR_OWNER_KEY = "gsc_bio_horror_revelation_turn_owner"
    _BIO_HORROR_TURN_KEY = "gsc_bio_horror_revelation_turn"
    _BIO_HORROR_PHASE_KEY = "gsc_bio_horror_revelation_expires_phase"
    _BIO_HORROR_SOURCE_KEY = "gsc_bio_horror_revelation_source"
    _GENE_TWISTED_MUSCLE_RULE_NAME = "Gene-Twisted Muscle"
    _GENE_TWISTED_MUSCLE_ACTIVE_KEY = "gsc_gene_twisted_muscle_active"
    _GENE_TWISTED_MUSCLE_BONUS_KEY = "gsc_gene_twisted_muscle_wound_bonus"
    _GENE_TWISTED_MUSCLE_OWNER_KEY = "gsc_gene_twisted_muscle_turn_owner"
    _GENE_TWISTED_MUSCLE_TURN_KEY = "gsc_gene_twisted_muscle_turn"
    _GENE_TWISTED_MUSCLE_PHASE_KEY = "gsc_gene_twisted_muscle_expires_phase"
    _GENE_TWISTED_MUSCLE_SOURCE_KEY = "gsc_gene_twisted_muscle_source"
    _HYPER_METABOLIC_VIGOUR_RULE_NAME = "Hyper-Metabolic Vigour"
    _HYPER_METABOLIC_VIGOUR_ACTIVE_KEY = "gsc_hyper_metabolic_vigour_active"
    _HYPER_METABOLIC_VIGOUR_OWNER_KEY = "gsc_hyper_metabolic_vigour_turn_owner"
    _HYPER_METABOLIC_VIGOUR_TURN_KEY = "gsc_hyper_metabolic_vigour_turn"
    _HYPER_METABOLIC_VIGOUR_PHASE_KEY = "gsc_hyper_metabolic_vigour_expires_phase"
    _HYPER_METABOLIC_VIGOUR_SOURCE_KEY = "gsc_hyper_metabolic_vigour_source"
    _STIMULATED_BIO_SURGE_RULE_NAME = "Stimulated Bio-Surge"
    _STIMULATED_BIO_SURGE_ACTIVE_KEY = "gsc_stimulated_bio_surge_active"
    _STIMULATED_BIO_SURGE_OWNER_KEY = "gsc_stimulated_bio_surge_turn_owner"
    _STIMULATED_BIO_SURGE_TURN_KEY = "gsc_stimulated_bio_surge_turn"
    _STIMULATED_BIO_SURGE_PHASE_KEY = "gsc_stimulated_bio_surge_expires_phase"
    _STIMULATED_BIO_SURGE_SOURCE_KEY = "gsc_stimulated_bio_surge_source"
    _STIMULATED_BIO_SURGE_PER_TARGET_KEY = "gsc_stimulated_bio_surge_bonus_per_target"
    _STIMULATED_BIO_SURGE_MAX_KEY = "gsc_stimulated_bio_surge_max_bonus"
    _A_PERFECT_AMBUSH_RULE_NAME = "A Perfect Ambush"
    _A_PERFECT_AMBUSH_SR_KEY = "gsc_a_perfect_ambush_effects"
    _A_PERFECT_AMBUSH_KEY_PREFIX = "gsc_a_perfect_ambush"
    _A_PERFECT_AMBUSH_KEYWORDS = ("SUSTAINED HITS 1", "IGNORES COVER")
    _A_CHINK_RULE_NAME = "A Chink in Their Armour"
    _A_CHINK_SR_KEY = "gsc_a_chink_in_their_armour_effects"
    _A_CHINK_KEY_PREFIX = "gsc_a_chink_in_their_armour"
    _A_CHINK_KEYWORDS = ("LETHAL HITS",)
    _A_CHINK_ENHANCEMENT_ID = "000009067003"
    _A_CHINK_NAME_KEY = "achinkintheirarmour"
    _INTEGRATED_TACTICS_RULE_NAME = "Integrated Tactics"
    _INTEGRATED_TACTICS_SOURCE_ACTIVE_KEY = "gsc_integrated_tactics_active"
    _INTEGRATED_TACTICS_SOURCE_TARGET_KEY = "gsc_integrated_tactics_target_unit_id"
    _INTEGRATED_TACTICS_SOURCE_OWNER_KEY = "gsc_integrated_tactics_turn_owner"
    _INTEGRATED_TACTICS_SOURCE_TURN_KEY = "gsc_integrated_tactics_turn"
    _INTEGRATED_TACTICS_SOURCE_PHASE_KEY = "gsc_integrated_tactics_expires_phase"
    _INTEGRATED_TACTICS_SOURCE_NAME_KEY = "gsc_integrated_tactics_source"
    _INTEGRATED_TACTICS_TARGET_ACTIVE_KEY = "gsc_integrated_tactics_overlapping_fire_active"
    _INTEGRATED_TACTICS_TARGET_OWNER_KEY = "gsc_integrated_tactics_overlapping_fire_owner"
    _INTEGRATED_TACTICS_TARGET_TURN_KEY = "gsc_integrated_tactics_overlapping_fire_turn"
    _INTEGRATED_TACTICS_TARGET_PHASE_KEY = "gsc_integrated_tactics_overlapping_fire_expires_phase"
    _INTEGRATED_TACTICS_TARGET_NAME_KEY = "gsc_integrated_tactics_overlapping_fire_source"
    _BROOD_BROTHERS_VOICE_OF_COMMAND_LOST_KEY = "gsc_brood_brothers_voice_of_command_lost"
    _BROOD_BROTHERS_FORBIDDEN_KEYWORDS = (
        "AIRCRAFT",
        "COMMISSAR",
        "MILITARUM TEMPESTUS",
        "OGRYN",
        "RATLING",
        "TECH-PRIEST ENGINSEER",
        "MINISTORUM PRIEST",
    )
    _BROOD_BROTHERS_FORBIDDEN_NAME_TOKENS = (
        "tech priest enginseer",
        "ministorum priest",
    )
    _MARTIAL_ESPIONAGE_RULE_NAME = "Martial Espionage"
    _MARTIAL_ESPIONAGE_ACTIVE_KEY = "enhancement_martial_espionage"
    _MARTIAL_ESPIONAGE_RANGE_KEY = "enhancement_martial_espionage_range"
    _MARTIAL_ESPIONAGE_AP_KEY = "enhancement_martial_espionage_ap_bonus"
    _MARTIAL_ESPIONAGE_SOURCE_KEY = "enhancement_martial_espionage_source"
    _MARTIAL_ESPIONAGE_LAST_USED_TURN_KEY = "enhancement_martial_espionage_last_used_turn"
    _MARTIAL_ESPIONAGE_LAST_USED_OWNER_KEY = "enhancement_martial_espionage_last_used_turn_owner"
    _FINAL_DAY_PSIONIC_PARASITISM_RULE_NAME = "Psionic Parasitism"
    _FINAL_DAY_PSIONIC_ACTIVE_KEY = "gsc_final_day_psionic_parasitism_active"
    _FINAL_DAY_PSIONIC_BONUS_KEY = "gsc_final_day_psionic_parasitism_hit_bonus"
    _FINAL_DAY_PSIONIC_OWNER_KEY = "gsc_final_day_psionic_parasitism_owner"
    _FINAL_DAY_PSIONIC_TURN_KEY = "gsc_final_day_psionic_parasitism_turn"
    _FINAL_DAY_PSIONIC_SOURCE_KEY = "gsc_final_day_psionic_parasitism_source"
    _FINAL_DAY_CATALYST_RULE_NAME = "Catalyst (Aura)"
    _FINAL_DAY_SYNAPTIC_AUGER_RULE_NAME = "Synaptic Auger"
    _FINAL_DAY_SYNAPTIC_AUGER_ACTIVE_KEY = "enhancement_synaptic_auger"
    _FINAL_DAY_SYNAPTIC_AUGER_MULTIPLIER_KEY = "enhancement_synaptic_auger_heal_multiplier"
    _FINAL_DAY_SYNAPTIC_AUGER_SOURCE_KEY = "enhancement_synaptic_auger_source"
    _FINAL_DAY_INHUMAN_INTEGRATION_RULE_NAME = "Inhuman Integration"
    _FINAL_DAY_INHUMAN_INTEGRATION_ACTIVE_KEY = "enhancement_inhuman_integration"
    _FINAL_DAY_INHUMAN_INTEGRATION_RANGE_KEY = "enhancement_inhuman_integration_range"
    _FINAL_DAY_INHUMAN_INTEGRATION_VALUE_KEY = "enhancement_inhuman_integration_sustained_hits_value"
    _FINAL_DAY_INHUMAN_INTEGRATION_SOURCE_KEY = "enhancement_inhuman_integration_source"
    _FINAL_DAY_GSC_EXCLUDED_NAME_TOKENS = (
        "purestrain genestealer",
        "patriarch",
    )
    _FINAL_DAY_TYRANID_REQUIRED_KEYWORD = "VANGUARD INVADER"
    _FINAL_DAY_TYRANID_FORBIDDEN_KEYWORDS = (
        "AIRCRAFT",
        "BROODLORD",
        "GENESTEALERS",
    )
    _RAPID_TAKEOVER_RULE_NAME = "Rapid Takeover"
    _RAPID_TAKEOVER_STICKY_SOURCE = "rapid_takeover"
    _RAPID_TAKEOVER_ATALAN_JACKALS_TOKEN = "atalan jackals"
    _OUTLANDER_CARTOGRAPHIC_DATA_LEECH_RULE_NAME = "Cartographic Data-leech"
    _OUTLANDER_CARTOGRAPHIC_DATA_LEECH_ACTIVE_KEY = "enhancement_cartographic_data_leech"
    _OUTLANDER_CARTOGRAPHIC_DATA_LEECH_BS_KEY = "enhancement_cartographic_data_leech_bs_improvement"
    _OUTLANDER_CARTOGRAPHIC_DATA_LEECH_SOURCE_KEY = "enhancement_cartographic_data_leech_source"
    _OUTLANDER_ASSAULT_COMMANDO_RULE_NAME = "Assault Commando"
    _OUTLANDER_ASSAULT_COMMANDO_ACTIVE_KEY = "enhancement_assault_commando"
    _OUTLANDER_ASSAULT_COMMANDO_SOURCE_KEY = "enhancement_assault_commando_source"
    _OUTLANDER_ASSAULT_COMMANDO_ATTACK_TYPE_KEY = "enhancement_assault_commando_attack_type"
    _OUTLANDER_STARFALL_SHELLS_RULE_NAME = "Starfall Shells"
    _OUTLANDER_STARFALL_SHELLS_ACTIVE_KEY = "enhancement_starfall_shells"
    _OUTLANDER_STARFALL_SHELLS_SOURCE_KEY = "enhancement_starfall_shells_source"
    _OUTLANDER_STARFALL_SHELLS_WEAPON_NAME_KEY = "enhancement_starfall_shells_weapon_name"
    _OUTLANDER_STARFALL_SHELLS_HIT_PENALTY_KEY = "enhancement_starfall_shells_hit_roll_penalty"
    _OUTLANDER_STARFALL_SHELLS_TARGET_ACTIVE_KEY = "gsc_starfall_shells_active"
    _OUTLANDER_STARFALL_SHELLS_TARGET_OWNER_KEY = "gsc_starfall_shells_owner"
    _OUTLANDER_STARFALL_SHELLS_TARGET_TURN_KEY = "gsc_starfall_shells_turn"
    _OUTLANDER_STARFALL_SHELLS_TARGET_SOURCE_KEY = "gsc_starfall_shells_source"
    _OUTLANDER_STARFALL_SHELLS_TARGET_PENALTY_KEY = "gsc_starfall_shells_hit_roll_penalty"
    _OUTLANDER_STARFALL_SHELLS_TARGET_EXPIRES_TIMING_KEY = "gsc_starfall_shells_expires_timing"
    _UNQUESTIONING_FANATICISM_RULE_NAME = "Unquestioning Fanaticism"
    _UNQUESTIONING_FANATICISM_ELIGIBLE_UNIT_PREFIXES = (
        "acolyte hybrids",
        "hybrid metamorphs",
        "neophyte hybrids",
    )
    _UNQUESTIONING_FANATICISM_FNP_LEADER_TOKENS = (
        "magus",
        "primus",
        "acolyte iconward",
    )
    _XENOCREED_DEEDS_THAT_SPEAK_TO_THE_MASSES_RULE_NAME = "Deeds That Speak to the Masses"
    _XENOCREED_DEEDS_THAT_SPEAK_TO_THE_MASSES_ACTIVE_KEY = "enhancement_deeds_that_speak_to_the_masses"
    _XENOCREED_DEEDS_THAT_SPEAK_TO_THE_MASSES_SOURCE_KEY = (
        "enhancement_deeds_that_speak_to_the_masses_source"
    )
    _XENOCREED_DEEDS_THAT_SPEAK_TO_THE_MASSES_BONUS_KEY = (
        "enhancement_deeds_that_speak_to_the_masses_resurgence_points_bonus"
    )

    @staticmethod
    def _attached_root(unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
            if root is not None:
                return root
        return unit

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _unit_is_genestealer_cults(self, unit) -> bool:
        return self._unit_has_keyword_or_faction(unit, "GENESTEALER CULTS", faction_id=self.faction_id)

    def _unit_is_astra_militarum(self, unit) -> bool:
        return self._unit_has_keyword(unit, "ASTRA MILITARUM")

    def _unit_is_tyranids(self, unit) -> bool:
        return self._unit_has_keyword(unit, "TYRANIDS")

    @staticmethod
    def _unit_has_ability_name(unit, ability_name: str) -> bool:
        target = str(ability_name or "").strip().lower()
        if not target:
            return False
        pools = [
            list(getattr(unit, "possible_abilities", []) or []),
            list(getattr(unit, "abilities", []) or []),
        ]
        for pool in pools:
            for ability in pool:
                name = ability if isinstance(ability, str) else getattr(ability, "name", "")
                if str(name or "").strip().lower() == target:
                    return True
        return False

    def _unit_is_tyranids_synapse(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None or not self._unit_is_tyranids(root):
            return False
        if self._unit_has_keyword(root, "SYNAPSE"):
            return True
        return self._unit_has_ability_name(root, "Synapse")

    @staticmethod
    def _unit_points(unit) -> int:
        get_cost = getattr(unit, "get_unit_cost", None)
        if callable(get_cost):
            value = get_cost()
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return 0
        value = getattr(unit, "points", 0)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _objective_sort_key(loc) -> tuple[str, float, float]:
        objective_id = str(get_entity_id(loc) or "")
        try:
            x = float(getattr(loc, "x", 0.0) or 0.0)
        except (TypeError, ValueError):
            x = 0.0
        try:
            y = float(getattr(loc, "y", 0.0) or 0.0)
        except (TypeError, ValueError):
            y = 0.0
        return (objective_id, x, y)

    @staticmethod
    def _brood_brothers_points_cap(points_limit: int) -> tuple[int, str]:
        if points_limit <= 1000:
            return 500, "Incursion"
        if points_limit <= 2000:
            return 1000, "Strike Force"
        return 1500, "Onslaught"

    @staticmethod
    def _unit_is_on_battlefield(unit) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        if str(getattr(unit, "reserve_status", "deployed") or "").strip().lower() != "deployed":
            return False
        is_in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            return False
        embarked = getattr(unit, "is_embarked", False)
        if callable(embarked):
            embarked = embarked()
        if bool(embarked):
            return False
        if getattr(unit, "embarked_in", None) is not None:
            return False
        return True

    @staticmethod
    def _resolve_game_map(game=None, *, game_map=None):
        if game_map is not None:
            return game_map
        if game is None:
            return None
        return getattr(game, "map", None)

    @staticmethod
    def _current_turn(*, game=None) -> int:
        try:
            return int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _current_turn_owner_id(*, game=None, player=None) -> str:
        current_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
        if current_player is not None:
            owner_id = str(getattr(current_player, "id", "") or "")
            if owner_id:
                return owner_id
        return str(getattr(player, "id", "") or "")

    @classmethod
    def _is_phase_owner_turn_active(
        cls,
        sr: dict,
        *,
        game=None,
        owner_key: str,
        turn_key: str,
        phase_key: str,
        owner_id: str = "",
    ) -> bool:
        if not isinstance(sr, dict):
            return False
        if game is None:
            return True
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        expected_phase = str(sr.get(phase_key, "") or "").strip().upper()
        if expected_phase and phase_name and expected_phase != phase_name:
            return False
        expected_owner = str(sr.get(owner_key, "") or "")
        if owner_id and expected_owner and expected_owner != owner_id:
            return False
        if expected_owner and not owner_id:
            current_player = getattr(game, "get_current_player", lambda: None)()
            current_owner = str(getattr(current_player, "id", "") or "")
            if current_owner and current_owner != expected_owner:
                return False
        try:
            expected_turn = int(sr.get(turn_key, 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0
        if expected_turn:
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
            if current_turn and current_turn != expected_turn:
                return False
        return True

    def _iter_unit_roots(self) -> list:
        if self.army is None:
            return []
        unique_roots = {}
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._attached_root(unit)
            root_id = str(get_entity_id(root) or "")
            if not root_id or root_id in unique_roots:
                continue
            unique_roots[root_id] = root
        return [unique_roots[k] for k in sorted(unique_roots.keys())]

    def _iter_attached_models(self, unit) -> list:
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        else:
            models = list(getattr(unit, "models", []) or [])
        return sorted(
            [model for model in models if model is not None],
            key=lambda m: str(get_entity_id(m) or ""),
        )

    def _iter_attached_members(self, unit) -> list:
        root = self._attached_root(unit)
        if root is None:
            return []
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        return sorted(
            [member for member in members if member is not None],
            key=lambda member: (str(get_entity_id(member) or ""), str(get_entity_id(root) or "")),
        )

    def _attached_member_active_enhancement_record(self, unit, *, active_key: str) -> tuple | None:
        root = self._attached_root(unit)
        if root is None:
            return None
        for member in self._iter_attached_members(root):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get(active_key, False)):
                continue
            get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            if bearer is None:
                continue
            return root, member, sr, bearer
        return None

    @staticmethod
    def _name_token(name: str) -> str:
        token = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower())
        return re.sub(r"\s+", " ", token).strip()

    @classmethod
    def _weapon_name_token(cls, weapon_name: str) -> str:
        return cls._name_token(weapon_name)

    def _unit_name_tokens(self, unit) -> set[str]:
        root = self._attached_root(unit)
        if root is None:
            return set()
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        out: set[str] = set()
        for member in members:
            token = self._name_token(getattr(member, "name", ""))
            if token:
                out.add(token)
        return out

    def _model_weapon_names(self, model, *, attack_type: str = "any") -> list[str]:
        attack = str(attack_type or "any").strip().lower()
        if attack not in ("any", "ranged", "melee"):
            attack = "any"
        by_key: dict[str, str] = {}
        for wargear in list(getattr(model, "wargear", []) or []):
            if attack == "ranged":
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
            elif attack == "melee":
                is_melee = getattr(wargear, "is_melee", None)
                if not callable(is_melee) or not bool(is_melee()):
                    continue
            weapon_name = str(getattr(wargear, "name", "") or "").strip()
            if not weapon_name:
                continue
            token = self._weapon_name_token(weapon_name)
            if not token or token in by_key:
                continue
            by_key[token] = weapon_name
        return [by_key[k] for k in sorted(by_key.keys())]

    def is_host_of_ascension(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Host of Ascension")

    def is_biosanctic_broodsurge(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Biosanctic Broodsurge")

    def is_brood_brother_auxilia(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Brood Brother Auxilia")

    def is_final_day(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Final Day")

    def is_outlander_claw(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Outlander Claw")

    def is_xenocreed_congregation(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Xenocreed Congregation")

    def outlander_claw_rapid_takeover_objective_control_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if not self.is_outlander_claw():
            return 0, ""
        if model is None:
            return 0, ""
        source_unit = unit if unit is not None else getattr(model, "parent_unit", None)
        root = self._attached_root(source_unit)
        if root is None:
            return 0, ""
        if not self._unit_in_army(root):
            return 0, ""
        if not self._unit_is_genestealer_cults(root):
            return 0, ""
        if not (self._unit_has_keyword(root, "MOUNTED") or self._unit_has_keyword(root, "VEHICLE")):
            return 0, ""
        is_battle_shocked = getattr(root, "is_battle_shocked", None)
        if callable(is_battle_shocked) and bool(is_battle_shocked()):
            return 0, ""
        return 1, self._RAPID_TAKEOVER_RULE_NAME

    def _is_outlander_claw_atalan_jackals_unit(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_genestealer_cults(root):
            return False
        return self._RAPID_TAKEOVER_ATALAN_JACKALS_TOKEN in self._unit_name_tokens(root)

    def apply_outlander_claw_rapid_takeover_sticky_objectives(self, *, game=None, game_map=None) -> int:
        if not self.is_outlander_claw() or self.army is None:
            return 0
        player = getattr(self.army, "player", None)
        if player is None:
            return 0
        resolved_map = self._resolve_game_map(game=game, game_map=game_map)
        if resolved_map is None:
            return 0

        objective_locations: list = []
        for obj in list(getattr(resolved_map, "objectives", []) or []):
            loc = getattr(obj, "location", None)
            if loc is None:
                loc = obj
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            update_control = getattr(loc, "update_control", None)
            if callable(update_control) and game is not None:
                update_control(game)
            objective_locations.append(loc)
        if not objective_locations:
            return 0
        objective_locations.sort(key=self._objective_sort_key)

        applied = 0
        for root in list(self._iter_unit_roots() or []):
            if root is None:
                continue
            if not self._is_outlander_claw_atalan_jackals_unit(root):
                continue
            if not self._unit_is_on_battlefield(root):
                continue
            within_objective = getattr(root, "is_within_objective_range", None)
            if not callable(within_objective):
                continue
            for loc in objective_locations:
                if getattr(loc, "controlling_player", None) is not player:
                    continue
                if not bool(within_objective(loc)):
                    continue
                if getattr(loc, "sticky_controller", None) is player:
                    continue
                set_sticky = getattr(loc, "set_sticky_control", None)
                if callable(set_sticky):
                    set_sticky(player, source=self._RAPID_TAKEOVER_STICKY_SOURCE)
                else:
                    loc.sticky_controller = player
                    loc.sticky_source = self._RAPID_TAKEOVER_STICKY_SOURCE
                    loc.controlling_player = player
                applied += 1
        return int(applied)

    def _outlander_cartographic_data_leech_record(self, unit) -> tuple | None:
        return self._attached_member_active_enhancement_record(
            unit,
            active_key=self._OUTLANDER_CARTOGRAPHIC_DATA_LEECH_ACTIVE_KEY,
        )

    def _outlander_assault_commando_record(self, unit) -> tuple | None:
        return self._attached_member_active_enhancement_record(
            unit,
            active_key=self._OUTLANDER_ASSAULT_COMMANDO_ACTIVE_KEY,
        )

    def _outlander_starfall_shells_record(self, unit) -> tuple | None:
        return self._attached_member_active_enhancement_record(
            unit,
            active_key=self._OUTLANDER_STARFALL_SHELLS_ACTIVE_KEY,
        )

    @staticmethod
    def _collection_contains_source_entity(items, source_entity_id: str) -> bool:
        source_id = str(source_entity_id or "").strip()
        if not source_id:
            return bool(list(items or []))
        for item in list(items or []):
            if item is None:
                continue
            if str(get_entity_id(item) or "") == source_id:
                return True
        return False

    def outlander_claw_cartographic_data_leech_bs_bonus(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        attack_instance=None,
        game=None,
    ) -> tuple[int, str]:
        del attack_instance  # Unused; parity with other modifier hooks.
        del game  # Unused; parity with other modifier hooks.
        if not self.is_outlander_claw():
            return 0, ""
        if attacker_model is None or weapon_profile is None:
            return 0, ""
        attacker_root = self._attached_root(getattr(attacker_model, "parent_unit", None))
        if attacker_root is None:
            return 0, ""
        if not self._unit_in_army(attacker_root):
            return 0, ""
        if not self._unit_is_genestealer_cults(attacker_root):
            return 0, ""

        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        is_ranged = getattr(parent_wargear, "is_ranged", None) if parent_wargear is not None else None
        if callable(is_ranged) and not bool(is_ranged()):
            return 0, ""

        firing_deck_sources = getattr(attacker_root, "_firing_deck_virtual_sources", None)
        profile_id = str(getattr(weapon_profile, "id", getattr(weapon_profile, "_id", "")) or "")
        is_firing_deck_weapon = bool(
            isinstance(firing_deck_sources, dict)
            and profile_id
            and profile_id in firing_deck_sources
        )
        if not is_firing_deck_weapon:
            weapon_name = str(getattr(parent_wargear, "name", "") or "").strip()
            if "(firing deck)" not in weapon_name.lower():
                return 0, ""

        for source_root in list(self._iter_unit_roots() or []):
            if source_root is None:
                continue
            embarked_in = self._attached_root(getattr(source_root, "embarked_in", None))
            if embarked_in is not attacker_root:
                continue
            source_record = self._outlander_cartographic_data_leech_record(source_root)
            if source_record is None:
                continue
            _record_root, _record_member, source_sr, _bearer = source_record
            try:
                bonus = int(source_sr.get(self._OUTLANDER_CARTOGRAPHIC_DATA_LEECH_BS_KEY, 1) or 1)
            except (TypeError, ValueError):
                bonus = 1
            if bonus <= 0:
                continue
            source_name = str(
                source_sr.get(
                    self._OUTLANDER_CARTOGRAPHIC_DATA_LEECH_SOURCE_KEY,
                    self._OUTLANDER_CARTOGRAPHIC_DATA_LEECH_RULE_NAME,
                )
                or self._OUTLANDER_CARTOGRAPHIC_DATA_LEECH_RULE_NAME
            ).strip() or self._OUTLANDER_CARTOGRAPHIC_DATA_LEECH_RULE_NAME
            return int(bonus), source_name
        return 0, ""

    def outlander_claw_assault_commando_hit_reroll_mods(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        attack_instance=None,
        game=None,
    ) -> dict:
        del target_unit  # Unused; parity with other reroll hooks.
        del attack_instance  # Unused; parity with other reroll hooks.
        del game  # Unused; parity with other reroll hooks.
        if not self.is_outlander_claw():
            return {}
        if attacker_model is None:
            return {}
        attacker_root = self._attached_root(getattr(attacker_model, "parent_unit", None))
        if attacker_root is None:
            return {}
        if not self._unit_in_army(attacker_root):
            return {}
        if not self._unit_is_genestealer_cults(attacker_root):
            return {}
        source_record = self._outlander_assault_commando_record(attacker_root)
        if source_record is None:
            return {}
        _source_root, _source_member, source_sr, _bearer = source_record

        attack_type = str(
            source_sr.get(self._OUTLANDER_ASSAULT_COMMANDO_ATTACK_TYPE_KEY, "ranged") or "ranged"
        ).strip().lower() or "ranged"
        if attack_type == "ranged" and weapon_profile is not None:
            parent_wargear = getattr(weapon_profile, "parent_wargear", None)
            is_ranged = getattr(parent_wargear, "is_ranged", None) if parent_wargear is not None else None
            if callable(is_ranged) and not bool(is_ranged()):
                return {}

        round_state = getattr(attacker_root, "round_state", None)
        if round_state is None:
            return {}
        if not bool(getattr(round_state, "disembarked_this_round", False)):
            return {}
        transport_id = str(getattr(round_state, "disembarked_from_transport_id", "") or "").strip()
        if not transport_id:
            return {}

        source_name = str(
            source_sr.get(self._OUTLANDER_ASSAULT_COMMANDO_SOURCE_KEY, self._OUTLANDER_ASSAULT_COMMANDO_RULE_NAME)
            or self._OUTLANDER_ASSAULT_COMMANDO_RULE_NAME
        ).strip() or self._OUTLANDER_ASSAULT_COMMANDO_RULE_NAME
        return {
            "reroll_full": True,
            "source": source_name,
        }

    def outlander_claw_starfall_shells_candidates_for_attacker(
        self,
        attacker_unit,
        *,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
    ) -> tuple[list, dict]:
        if not self.is_outlander_claw():
            return [], {}
        attacker_root = self._attached_root(attacker_unit)
        if attacker_root is None:
            return [], {}
        if not self._unit_in_army(attacker_root):
            return [], {}
        if not self._unit_is_genestealer_cults(attacker_root):
            return [], {}
        if not isinstance(hits_by_target, dict) or not isinstance(hit_models_by_target_weapon, dict):
            return [], {}

        source_record = self._outlander_starfall_shells_record(attacker_root)
        if source_record is None:
            return [], {}
        _source_root, _source_member, source_sr, bearer = source_record
        source_name = str(
            source_sr.get(self._OUTLANDER_STARFALL_SHELLS_SOURCE_KEY, self._OUTLANDER_STARFALL_SHELLS_RULE_NAME)
            or self._OUTLANDER_STARFALL_SHELLS_RULE_NAME
        ).strip() or self._OUTLANDER_STARFALL_SHELLS_RULE_NAME
        weapon_name = str(
            source_sr.get(self._OUTLANDER_STARFALL_SHELLS_WEAPON_NAME_KEY, "cult sniper rifle") or "cult sniper rifle"
        ).strip() or "cult sniper rifle"
        weapon_key = self._weapon_name_token(weapon_name)
        if not weapon_key:
            return [], {}
        try:
            hit_roll_penalty = int(source_sr.get(self._OUTLANDER_STARFALL_SHELLS_HIT_PENALTY_KEY, 1) or 1)
        except (TypeError, ValueError):
            hit_roll_penalty = 1
        source_model_id = str(get_entity_id(bearer) or "")

        candidates_by_id: dict[str, object] = {}
        for target_unit, hits in list(hits_by_target.items() or []):
            try:
                if int(hits or 0) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            target_root = self._attached_root(target_unit)
            if target_root is None:
                continue
            target_army = getattr(target_root, "get_parent_army", lambda: None)()
            if target_army is self.army:
                continue
            if not bool(getattr(target_root, "is_alive", lambda: True)()):
                continue
            target_map = hit_models_by_target_weapon.get(target_unit)
            if not isinstance(target_map, dict):
                target_map = hit_models_by_target_weapon.get(target_root)
            if not isinstance(target_map, dict):
                continue
            hit_models = target_map.get(weapon_key)
            if not self._collection_contains_source_entity(hit_models, source_model_id):
                continue
            target_id = str(get_entity_id(target_root) or "")
            if not target_id or target_id in candidates_by_id:
                continue
            candidates_by_id[target_id] = target_root

        candidate_ids = sorted(candidates_by_id.keys())
        return [candidates_by_id[target_id] for target_id in candidate_ids], {
            "source": source_name,
            "hit_roll_penalty": int(max(1, hit_roll_penalty)),
        }

    def _xenocreed_unquestioning_fanaticism_bodyguard_eligible(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_genestealer_cults(root):
            return False
        tokens = self._unit_name_tokens(root)
        for token in tokens:
            for prefix in self._UNQUESTIONING_FANATICISM_ELIGIBLE_UNIT_PREFIXES:
                if token.startswith(prefix):
                    return True
        return False

    def _xenocreed_attached_character_leaders(self, unit) -> list:
        root = self._attached_root(unit)
        if root is None:
            return []
        leaders = sorted(
            [leader for leader in list(getattr(root, "attached_leaders", []) or []) if leader is not None],
            key=lambda leader: str(get_entity_id(leader) or ""),
        )
        out: list = []
        for leader in leaders:
            if not self._unit_in_army(leader):
                continue
            if not bool(getattr(leader, "is_attached_leader", False)):
                continue
            models = list(getattr(leader, "models", []) or [])
            if not models:
                continue
            has_alive_model = False
            has_character_model = False
            for model in models:
                if model is None:
                    continue
                is_alive = getattr(model, "is_alive", True)
                if callable(is_alive):
                    is_alive = is_alive()
                if not bool(is_alive):
                    continue
                has_alive_model = True
                if bool(getattr(model, "is_character", False)):
                    has_character_model = True
                    break
            if not has_alive_model:
                continue
            if not has_character_model and not self._unit_has_keyword(leader, "CHARACTER"):
                continue
            out.append(leader)
        return out

    def xenocreed_unquestioning_fanaticism_reroll_advance_applies(self, unit) -> bool:
        if not self.is_xenocreed_congregation():
            return False
        if not self._xenocreed_unquestioning_fanaticism_bodyguard_eligible(unit):
            return False
        return bool(self._xenocreed_attached_character_leaders(unit))

    def xenocreed_unquestioning_fanaticism_reroll_charge_applies(self, unit) -> bool:
        return self.xenocreed_unquestioning_fanaticism_reroll_advance_applies(unit)

    def xenocreed_unquestioning_fanaticism_fnp(self, unit, *, target_model=None) -> tuple[int, str]:
        if not self.is_xenocreed_congregation():
            return 0, ""
        if target_model is None:
            return 0, ""
        root = self._attached_root(unit)
        if root is None:
            return 0, ""
        if not self._xenocreed_unquestioning_fanaticism_bodyguard_eligible(root):
            return 0, ""
        if not self._xenocreed_attached_character_leaders(root):
            return 0, ""

        model_unit = getattr(target_model, "parent_unit", None)
        model_root = self._attached_root(model_unit)
        if model_unit is None or model_root is not root:
            return 0, ""
        if not bool(getattr(model_unit, "is_attached_leader", False)):
            return 0, ""
        if not bool(getattr(target_model, "is_character", False)) and not self._unit_has_keyword(model_unit, "CHARACTER"):
            return 0, ""

        leader_tokens = self._unit_name_tokens(model_unit)
        for token in leader_tokens:
            if token in self._UNQUESTIONING_FANATICISM_FNP_LEADER_TOKENS:
                return 3, self._UNQUESTIONING_FANATICISM_RULE_NAME
        return 0, ""

    def xenocreed_additional_starting_resurgence_points(self) -> int:
        if not self.is_xenocreed_congregation():
            return 0
        total = 0
        seen_sources: set[str] = set()
        for root in self._iter_unit_roots():
            if root is None:
                continue
            for member in self._iter_attached_members(root):
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if not bool(sr.get(self._XENOCREED_DEEDS_THAT_SPEAK_TO_THE_MASSES_ACTIVE_KEY, False)):
                    continue
                member_id = str(get_entity_id(member) or "")
                if member_id and member_id in seen_sources:
                    continue
                if member_id:
                    seen_sources.add(member_id)
                try:
                    bonus = int(sr.get(self._XENOCREED_DEEDS_THAT_SPEAK_TO_THE_MASSES_BONUS_KEY, 2) or 2)
                except (TypeError, ValueError):
                    bonus = 2
                total += max(0, int(bonus))
        return int(total)

    def _integrated_tactics_source_eligible(self, unit) -> bool:
        if not self.is_brood_brother_auxilia():
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_on_battlefield(root):
            return False
        return bool(self._unit_is_astra_militarum(root))

    def integrated_tactics_source_eligible(self, unit) -> bool:
        return self._integrated_tactics_source_eligible(unit)

    def integrated_tactics_target_eligible(self, source_unit, target_unit, *, game=None, game_map=None) -> bool:
        if not self._integrated_tactics_source_eligible(source_unit):
            return False
        source_root = self._attached_root(source_unit)
        target_root = self._attached_root(target_unit)
        if source_root is None or target_root is None:
            return False
        if not self._unit_is_on_battlefield(target_root):
            return False
        target_army = getattr(target_root, "get_parent_army", lambda: None)()
        if target_army is not None and target_army is self.army:
            return False

        local_map = self._resolve_game_map(game, game_map=game_map)
        if local_map is not None:
            get_distance = getattr(local_map, "get_distance_between_units", None)
            if callable(get_distance):
                try:
                    distance = float(get_distance(source_root, target_root))
                except (TypeError, ValueError):
                    return False
                if distance > 18.0:
                    return False
            has_los = getattr(source_root, "_attacking_unit_has_any_los_to_target_unit", None)
            if callable(has_los) and not bool(has_los(target_root, local_map)):
                return False
        return True

    def integrated_tactics_target_candidates_for_unit(self, source_unit, *, game=None, game_map=None) -> list:
        if not self._integrated_tactics_source_eligible(source_unit):
            return []
        source_root = self._attached_root(source_unit)
        if source_root is None:
            return []

        local_map = self._resolve_game_map(game, game_map=game_map)
        player = getattr(self.army, "player", None) if self.army is not None else None
        enemy_units = []
        if game is not None and player is not None and callable(getattr(game, "get_enemy_units", None)):
            enemy_units = list(game.get_enemy_units(player) or [])
        elif local_map is not None and callable(getattr(local_map, "get_enemy_units", None)):
            enemy_units = list(local_map.get_enemy_units(source_root) or [])

        unique: dict[str, object] = {}
        for unit in list(enemy_units or []):
            root = self._attached_root(unit)
            target_id = str(get_entity_id(root) or "")
            if not target_id or target_id in unique:
                continue
            if not self.integrated_tactics_target_eligible(
                source_root,
                root,
                game=game,
                game_map=local_map,
            ):
                continue
            unique[target_id] = root
        return [unique[k] for k in sorted(unique.keys())]

    def _martial_espionage_source_records(self) -> list[tuple]:
        if not self.is_brood_brother_auxilia():
            return []
        out: list[tuple] = []
        for source_root in self._iter_unit_roots():
            if source_root is None:
                continue
            if not self._unit_in_army(source_root):
                continue
            if not self._unit_is_on_battlefield(source_root):
                continue
            if not self._unit_is_genestealer_cults(source_root):
                continue
            members = list(getattr(source_root, "get_attached_unit_members", lambda: [source_root])() or [])
            if not members:
                members = [source_root]
            members = sorted(
                [member for member in members if member is not None],
                key=lambda member: (str(get_entity_id(member) or ""), str(get_entity_id(source_root) or "")),
            )
            for source_member in members:
                source_sr = getattr(source_member, "special_rules", None)
                if not isinstance(source_sr, dict):
                    continue
                if not bool(source_sr.get(self._MARTIAL_ESPIONAGE_ACTIVE_KEY, False)):
                    continue
                get_bearer = getattr(source_member, "_get_enhancement_bearer_model", None)
                bearer = get_bearer() if callable(get_bearer) else None
                if bearer is None:
                    continue
                out.append((source_root, source_member, source_sr, bearer))
        return out

    def _martial_espionage_source_record(self, source_unit, *, source_member=None) -> tuple | None:
        source_root = self._attached_root(source_unit)
        if source_root is None:
            return None
        member = source_member if source_member is not None else source_root
        if member is None:
            return None
        source_sr = getattr(member, "special_rules", None)
        if not isinstance(source_sr, dict):
            return None
        if not bool(source_sr.get(self._MARTIAL_ESPIONAGE_ACTIVE_KEY, False)):
            return None
        get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
        bearer = get_bearer() if callable(get_bearer) else None
        if bearer is None:
            return None
        return source_root, member, source_sr, bearer

    def _martial_espionage_usage_key(self, *, game=None, player=None) -> tuple[int, str]:
        return self._current_turn(game=game), self._current_turn_owner_id(game=game, player=player)

    def _martial_espionage_source_used_this_turn(self, source_unit, *, game=None, player=None) -> bool:
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict):
            return False
        current_turn, current_owner = self._martial_espionage_usage_key(game=game, player=player)
        try:
            used_turn = int(source_sr.get(self._MARTIAL_ESPIONAGE_LAST_USED_TURN_KEY, 0) or 0)
        except (TypeError, ValueError):
            used_turn = 0
        used_owner = str(source_sr.get(self._MARTIAL_ESPIONAGE_LAST_USED_OWNER_KEY, "") or "")
        return bool(used_turn and used_turn == int(current_turn) and used_owner == str(current_owner))

    def _mark_martial_espionage_used(self, source_unit, *, game=None, player=None) -> None:
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict):
            source_sr = {}
        current_turn, current_owner = self._martial_espionage_usage_key(game=game, player=player)
        source_sr[self._MARTIAL_ESPIONAGE_LAST_USED_TURN_KEY] = int(current_turn)
        source_sr[self._MARTIAL_ESPIONAGE_LAST_USED_OWNER_KEY] = str(current_owner)
        source_unit.special_rules = source_sr

    def martial_espionage_target_eligible(
        self,
        source_unit,
        target_unit,
        *,
        source_member=None,
        game=None,
        game_map=None,
    ) -> bool:
        source_record = self._martial_espionage_source_record(source_unit, source_member=source_member)
        if source_record is None:
            return False
        source_root, _source_member, source_sr, bearer = source_record
        target_root = self._attached_root(target_unit)
        if target_root is None:
            return False
        if not self._unit_in_army(target_root):
            return False
        if not self._unit_is_on_battlefield(target_root):
            return False
        if not self._unit_is_astra_militarum(target_root):
            return False
        if not (self._unit_has_keyword(target_root, "INFANTRY") or self._unit_has_keyword(target_root, "MOUNTED")):
            return False
        try:
            range_in = float(source_sr.get(self._MARTIAL_ESPIONAGE_RANGE_KEY, 9.0) or 9.0)
        except (TypeError, ValueError):
            range_in = 9.0
        if range_in < 0.0:
            range_in = 0.0
        from ..utility.aura_utils import model_within_range_of_unit

        return bool(model_within_range_of_unit(bearer, target_root, range_in, use_attached_aggregate=True))

    def martial_espionage_source_candidates_for_shooting_unit(self, target_unit, *, game=None, game_map=None) -> list[tuple]:
        if not self.is_brood_brother_auxilia():
            return []
        target_root = self._attached_root(target_unit)
        if target_root is None:
            return []
        local_map = self._resolve_game_map(game=game, game_map=game_map)
        out: list[tuple] = []
        for source_root, source_member, source_sr, bearer in self._martial_espionage_source_records():
            if self._martial_espionage_source_used_this_turn(source_member, game=game):
                continue
            if not self.martial_espionage_target_eligible(
                source_root,
                target_root,
                source_member=source_member,
                game=game,
                game_map=local_map,
            ):
                continue
            out.append((source_root, source_member, source_sr, bearer))
        out.sort(key=lambda item: (str(get_entity_id(item[1]) or ""), str(get_entity_id(item[0]) or "")))
        return out

    def apply_martial_espionage_choice(
        self,
        source_unit,
        *,
        source_member=None,
        target_unit=None,
        game=None,
        player=None,
    ) -> dict | None:
        if target_unit is None:
            return None
        source_record = self._martial_espionage_source_record(source_unit, source_member=source_member)
        if source_record is None:
            return None
        source_root, source_member_unit, source_sr, _bearer = source_record
        target_root = self._attached_root(target_unit)
        if target_root is None:
            return None
        if self._martial_espionage_source_used_this_turn(source_member_unit, game=game, player=player):
            return None
        if not self.martial_espionage_target_eligible(
            source_root,
            target_root,
            source_member=source_member_unit,
            game=game,
        ):
            return None
        apply_bonus = getattr(target_root, "apply_selected_to_shoot_unit_ranged_weapon_bonuses", None)
        if not callable(apply_bonus):
            return None
        try:
            ap_bonus = int(source_sr.get(self._MARTIAL_ESPIONAGE_AP_KEY, 1) or 1)
        except (TypeError, ValueError):
            ap_bonus = 1
        ap_bonus = max(1, int(ap_bonus))
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() or "SHOOTING_PHASE"
        source_name = str(source_sr.get(self._MARTIAL_ESPIONAGE_SOURCE_KEY, "") or self._MARTIAL_ESPIONAGE_RULE_NAME).strip()
        current_turn, current_owner = self._martial_espionage_usage_key(game=game, player=player)
        source_id = str(get_entity_id(source_member_unit) or get_entity_id(source_root) or "")
        target_id = str(get_entity_id(target_root) or "")
        applied = int(
            apply_bonus(
                key_prefix=f"martial_espionage:{source_id}:{target_id}:{current_turn}:{current_owner}",
                source=(source_name or self._MARTIAL_ESPIONAGE_RULE_NAME),
                ap_bonus=int(ap_bonus),
                expires_phase=phase_name,
                target_root=target_root,
            )
            or 0
        )
        if applied <= 0:
            return None
        self._mark_martial_espionage_used(source_member_unit, game=game, player=player)
        return {
            "action": "apply",
            "source_unit_id": str(get_entity_id(source_root) or ""),
            "source_member_unit_id": str(get_entity_id(source_member_unit) or ""),
            "target_unit_id": target_id,
            "source_model_id": str(get_entity_id(getattr(source_member_unit, "_get_enhancement_bearer_model", lambda: None)() or "") or ""),
            "ap_bonus": int(ap_bonus),
            "source": source_name or self._MARTIAL_ESPIONAGE_RULE_NAME,
            "applied_weapon_count": int(applied),
            "expires_phase": phase_name,
        }

    def _clear_integrated_tactics_source_lock(self, unit) -> None:
        root = self._attached_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            self._INTEGRATED_TACTICS_SOURCE_ACTIVE_KEY,
            self._INTEGRATED_TACTICS_SOURCE_TARGET_KEY,
            self._INTEGRATED_TACTICS_SOURCE_OWNER_KEY,
            self._INTEGRATED_TACTICS_SOURCE_TURN_KEY,
            self._INTEGRATED_TACTICS_SOURCE_PHASE_KEY,
            self._INTEGRATED_TACTICS_SOURCE_NAME_KEY,
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _clear_integrated_tactics_target_mark(self, unit) -> None:
        root = self._attached_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            self._INTEGRATED_TACTICS_TARGET_ACTIVE_KEY,
            self._INTEGRATED_TACTICS_TARGET_OWNER_KEY,
            self._INTEGRATED_TACTICS_TARGET_TURN_KEY,
            self._INTEGRATED_TACTICS_TARGET_PHASE_KEY,
            self._INTEGRATED_TACTICS_TARGET_NAME_KEY,
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def apply_integrated_tactics_choice(
        self,
        source_unit,
        *,
        target_unit=None,
        skip: bool = False,
        game=None,
        player=None,
    ) -> dict | None:
        if not self._integrated_tactics_source_eligible(source_unit):
            return None
        source_root = self._attached_root(source_unit)
        if source_root is None:
            return None

        self._clear_integrated_tactics_source_lock(source_root)
        if skip:
            return {
                "action": "skip",
                "source_unit_id": str(get_entity_id(source_root) or ""),
            }

        target_root = self._attached_root(target_unit)
        if target_root is None:
            return None
        if not self.integrated_tactics_target_eligible(source_root, target_root, game=game):
            return None

        owner_player = player if player is not None else getattr(self.army, "player", None)
        owner_id = str(getattr(owner_player, "id", "") or "")
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            turn = 0

        source_sr = getattr(source_root, "special_rules", None)
        if not isinstance(source_sr, dict):
            source_sr = {}
        source_sr[self._INTEGRATED_TACTICS_SOURCE_ACTIVE_KEY] = True
        source_sr[self._INTEGRATED_TACTICS_SOURCE_TARGET_KEY] = str(get_entity_id(target_root) or "")
        source_sr[self._INTEGRATED_TACTICS_SOURCE_OWNER_KEY] = owner_id
        source_sr[self._INTEGRATED_TACTICS_SOURCE_TURN_KEY] = int(turn or 0)
        source_sr[self._INTEGRATED_TACTICS_SOURCE_PHASE_KEY] = "SHOOTING_PHASE"
        source_sr[self._INTEGRATED_TACTICS_SOURCE_NAME_KEY] = self._INTEGRATED_TACTICS_RULE_NAME
        source_root.special_rules = source_sr

        target_sr = getattr(target_root, "special_rules", None)
        if not isinstance(target_sr, dict):
            target_sr = {}
        target_sr[self._INTEGRATED_TACTICS_TARGET_ACTIVE_KEY] = True
        target_sr[self._INTEGRATED_TACTICS_TARGET_OWNER_KEY] = owner_id
        target_sr[self._INTEGRATED_TACTICS_TARGET_TURN_KEY] = int(turn or 0)
        target_sr[self._INTEGRATED_TACTICS_TARGET_PHASE_KEY] = "SHOOTING_PHASE"
        target_sr[self._INTEGRATED_TACTICS_TARGET_NAME_KEY] = self._INTEGRATED_TACTICS_RULE_NAME
        target_root.special_rules = target_sr

        return {
            "action": "mark",
            "source_unit_id": str(get_entity_id(source_root) or ""),
            "target_unit_id": str(get_entity_id(target_root) or ""),
            "source": self._INTEGRATED_TACTICS_RULE_NAME,
        }

    def integrated_tactics_target_locked_to(self, source_unit, target_unit, *, game=None) -> bool:
        if not self.is_brood_brother_auxilia():
            return True
        source_root = self._attached_root(source_unit)
        if source_root is None:
            return True
        if not self._unit_in_army(source_root):
            return True
        if not self._unit_is_astra_militarum(source_root):
            return True
        sr = getattr(source_root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(self._INTEGRATED_TACTICS_SOURCE_ACTIVE_KEY)):
            return True
        if not self._is_phase_owner_turn_active(
            sr,
            game=game,
            owner_key=self._INTEGRATED_TACTICS_SOURCE_OWNER_KEY,
            turn_key=self._INTEGRATED_TACTICS_SOURCE_TURN_KEY,
            phase_key=self._INTEGRATED_TACTICS_SOURCE_PHASE_KEY,
        ):
            return True
        expected_target_id = str(sr.get(self._INTEGRATED_TACTICS_SOURCE_TARGET_KEY, "") or "")
        if not expected_target_id:
            return True
        target_root = self._attached_root(target_unit)
        current_target_id = str(get_entity_id(target_root) or "")
        if not current_target_id:
            return True
        return bool(current_target_id == expected_target_id)

    def integrated_tactics_hit_bonus(self, attacker_model, target_unit, *, game=None, weapon_profile=None) -> tuple[int, str]:
        if not self.is_brood_brother_auxilia():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        if weapon_profile is not None:
            is_melee = getattr(weapon_profile, "is_melee", None)
            if callable(is_melee) and bool(is_melee()):
                return 0, ""

        attacker_unit = self._attached_root(getattr(attacker_model, "parent_unit", None))
        if attacker_unit is None or not self._unit_in_army(attacker_unit):
            return 0, ""
        if not self._unit_is_genestealer_cults(attacker_unit):
            return 0, ""
        if self._unit_is_astra_militarum(attacker_unit):
            return 0, ""

        target_root = self._attached_root(target_unit)
        if target_root is None:
            return 0, ""
        target_sr = getattr(target_root, "special_rules", None)
        if not isinstance(target_sr, dict):
            return 0, ""
        if not bool(target_sr.get(self._INTEGRATED_TACTICS_TARGET_ACTIVE_KEY)):
            return 0, ""
        owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
        if not self._is_phase_owner_turn_active(
            target_sr,
            game=game,
            owner_key=self._INTEGRATED_TACTICS_TARGET_OWNER_KEY,
            turn_key=self._INTEGRATED_TACTICS_TARGET_TURN_KEY,
            phase_key=self._INTEGRATED_TACTICS_TARGET_PHASE_KEY,
            owner_id=owner_id,
        ):
            return 0, ""
        return 1, self._INTEGRATED_TACTICS_RULE_NAME

    def _final_day_is_eligible_gsc_target(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_on_battlefield(root):
            return False
        if not self._unit_is_genestealer_cults(root):
            return False
        name_tokens = self._unit_name_tokens(root)
        for token in self._FINAL_DAY_GSC_EXCLUDED_NAME_TOKENS:
            if token in name_tokens:
                return False
        return True

    def _final_day_is_eligible_tyranid_target(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_on_battlefield(root):
            return False
        return bool(self._unit_is_tyranids(root))

    def final_day_psionic_parasitism_synapse_eligible(self, unit) -> bool:
        if not self.is_final_day():
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_on_battlefield(root):
            return False
        return bool(self._unit_is_tyranids_synapse(root))

    def final_day_psionic_parasitism_synapse_units(self) -> list:
        if not self.is_final_day():
            return []
        out: dict[str, object] = {}
        for root in self._iter_unit_roots():
            if not self.final_day_psionic_parasitism_synapse_eligible(root):
                continue
            unit_id = str(get_entity_id(root) or "")
            if unit_id:
                out[unit_id] = root
        return [out[k] for k in sorted(out.keys())]

    def final_day_psionic_parasitism_pair_eligible(
        self,
        synapse_unit,
        gsc_unit,
        tyranids_unit,
        *,
        game=None,
        game_map=None,
    ) -> bool:
        if not self.final_day_psionic_parasitism_synapse_eligible(synapse_unit):
            return False
        synapse_root = self._attached_root(synapse_unit)
        gsc_root = self._attached_root(gsc_unit)
        tyr_root = self._attached_root(tyranids_unit)
        if synapse_root is None or gsc_root is None or tyr_root is None:
            return False
        if not self._final_day_is_eligible_gsc_target(gsc_root):
            return False
        if not self._final_day_is_eligible_tyranid_target(tyr_root):
            return False
        local_map = self._resolve_game_map(game, game_map=game_map)
        if local_map is not None:
            get_distance = getattr(local_map, "get_distance_between_units", None)
            if callable(get_distance):
                try:
                    gsc_distance = float(get_distance(synapse_root, gsc_root))
                    tyr_distance = float(get_distance(synapse_root, tyr_root))
                except (TypeError, ValueError):
                    return False
                if gsc_distance > 9.0 or tyr_distance > 9.0:
                    return False
            has_los = getattr(synapse_root, "_attacking_unit_has_any_los_to_target_unit", None)
            if callable(has_los):
                if not bool(has_los(gsc_root, local_map)):
                    return False
                if not bool(has_los(tyr_root, local_map)):
                    return False
        return True

    def final_day_psionic_parasitism_pair_candidates_for_synapse(self, synapse_unit, *, game=None, game_map=None) -> list[tuple]:
        if not self.final_day_psionic_parasitism_synapse_eligible(synapse_unit):
            return []
        synapse_root = self._attached_root(synapse_unit)
        if synapse_root is None:
            return []
        roots = self._iter_unit_roots()
        gsc_targets = [root for root in roots if self._final_day_is_eligible_gsc_target(root)]
        tyr_targets = [root for root in roots if self._final_day_is_eligible_tyranid_target(root)]
        local_map = self._resolve_game_map(game, game_map=game_map)
        pairs: dict[str, tuple] = {}
        for gsc_root in gsc_targets:
            gsc_id = str(get_entity_id(gsc_root) or "")
            if not gsc_id:
                continue
            for tyr_root in tyr_targets:
                tyr_id = str(get_entity_id(tyr_root) or "")
                if not tyr_id:
                    continue
                if not self.final_day_psionic_parasitism_pair_eligible(
                    synapse_root,
                    gsc_root,
                    tyr_root,
                    game=game,
                    game_map=local_map,
                ):
                    continue
                pairs[f"{gsc_id}:{tyr_id}"] = (gsc_root, tyr_root)
        return [pairs[k] for k in sorted(pairs.keys())]

    def _heal_one_model_in_unit(self, unit, amount: int, *, preferred_model_id: str = "") -> tuple[int, str]:
        root = self._attached_root(unit)
        if root is None:
            return 0, ""
        try:
            heal_amount = int(amount or 0)
        except (TypeError, ValueError):
            heal_amount = 0
        if heal_amount <= 0:
            return 0, ""
        models = self._iter_attached_models(root)
        preferred_id = str(preferred_model_id or "").strip()
        if preferred_id:
            models.sort(
                key=lambda model: (
                    0 if str(get_entity_id(model) or "") == preferred_id else 1,
                    str(get_entity_id(model) or ""),
                )
            )
        for model in models:
            is_alive = getattr(model, "is_alive", True)
            if callable(is_alive):
                is_alive = is_alive()
            if not bool(is_alive):
                continue
            current_wounds = int(getattr(model, "wounds", 0) or 0)
            base_wounds = int(getattr(model, "_base_wounds", current_wounds) or current_wounds)
            missing = int(base_wounds - current_wounds)
            if missing <= 0:
                continue
            healed = min(int(heal_amount), int(missing))
            heal_fn = getattr(model, "heal", None)
            if callable(heal_fn):
                heal_fn(int(healed))
            else:
                setattr(model, "wounds", int(current_wounds + healed))
            return int(healed), str(get_entity_id(model) or "")
        return 0, ""

    def _final_day_target_within_range_of_friendly_tyranids(
        self,
        target_unit,
        *,
        range_in: float,
        game=None,
        game_map=None,
    ) -> bool:
        if not self.is_final_day():
            return False
        target_root = self._attached_root(target_unit)
        if target_root is None:
            return False
        target_army = getattr(target_root, "get_parent_army", lambda: None)()
        if target_army is self.army:
            return False
        try:
            max_range = float(range_in or 0.0)
        except (TypeError, ValueError):
            max_range = 0.0
        if max_range <= 0.0:
            return False
        local_map = self._resolve_game_map(game=game, game_map=game_map)
        get_distance = getattr(local_map, "get_distance_between_units", None) if local_map is not None else None
        if not callable(get_distance):
            return False
        for tyr_root in self._iter_unit_roots():
            if not self._unit_is_tyranids(tyr_root):
                continue
            if not self._unit_is_on_battlefield(tyr_root):
                continue
            try:
                distance = float(get_distance(tyr_root, target_root))
            except (TypeError, ValueError):
                continue
            if distance <= max_range:
                return True
        return False

    def _final_day_synaptic_auger_record(self, unit) -> tuple | None:
        return self._attached_member_active_enhancement_record(
            unit,
            active_key=self._FINAL_DAY_SYNAPTIC_AUGER_ACTIVE_KEY,
        )

    def _final_day_inhuman_integration_record(self, unit) -> tuple | None:
        return self._attached_member_active_enhancement_record(
            unit,
            active_key=self._FINAL_DAY_INHUMAN_INTEGRATION_ACTIVE_KEY,
        )

    def apply_final_day_psionic_parasitism_choice(
        self,
        synapse_unit,
        *,
        gsc_unit=None,
        tyranids_unit=None,
        skip: bool = False,
        game=None,
        player=None,
        mortal_wounds: int = 0,
    ) -> dict | None:
        if not self.final_day_psionic_parasitism_synapse_eligible(synapse_unit):
            return None
        synapse_root = self._attached_root(synapse_unit)
        if synapse_root is None:
            return None
        if skip:
            return {
                "action": "skip",
                "synapse_unit_id": str(get_entity_id(synapse_root) or ""),
            }

        gsc_root = self._attached_root(gsc_unit)
        tyr_root = self._attached_root(tyranids_unit)
        if gsc_root is None or tyr_root is None:
            return None
        if not self.final_day_psionic_parasitism_pair_eligible(synapse_root, gsc_root, tyr_root, game=game):
            return None

        try:
            mortal = int(mortal_wounds or 0)
        except (TypeError, ValueError):
            mortal = 0
        if mortal < 0:
            mortal = 0

        game_map = getattr(game, "map", None) if game is not None else None
        if mortal > 0:
            apply_mortals = getattr(synapse_root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortals):
                apply_mortals(gsc_root, int(mortal), game_map=game_map)

        heal_amount = int(mortal)
        preferred_model_id = ""
        synaptic_auger_record = self._final_day_synaptic_auger_record(tyr_root)
        if synaptic_auger_record is not None:
            _source_root, _source_member, source_sr, bearer = synaptic_auger_record
            current_wounds = int(getattr(bearer, "wounds", 0) or 0)
            base_wounds = int(getattr(bearer, "_base_wounds", current_wounds) or current_wounds)
            if int(base_wounds - current_wounds) > 0 and heal_amount > 0:
                preferred_model_id = str(get_entity_id(bearer) or "")
                try:
                    heal_multiplier = int(source_sr.get(self._FINAL_DAY_SYNAPTIC_AUGER_MULTIPLIER_KEY, 2) or 2)
                except (TypeError, ValueError):
                    heal_multiplier = 2
                heal_amount = int(heal_amount) * int(max(2, heal_multiplier))
        healed, healed_model_id = self._heal_one_model_in_unit(
            tyr_root,
            int(heal_amount),
            preferred_model_id=preferred_model_id,
        )
        owner_player = player if player is not None else getattr(self.army, "player", None)
        owner_id = str(getattr(owner_player, "id", "") or "")
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            turn = 0
        tyr_sr = getattr(tyr_root, "special_rules", None)
        if not isinstance(tyr_sr, dict):
            tyr_sr = {}
        tyr_sr[self._FINAL_DAY_PSIONIC_ACTIVE_KEY] = True
        tyr_sr[self._FINAL_DAY_PSIONIC_BONUS_KEY] = 1
        tyr_sr[self._FINAL_DAY_PSIONIC_OWNER_KEY] = owner_id
        tyr_sr[self._FINAL_DAY_PSIONIC_TURN_KEY] = int(turn or 0)
        tyr_sr[self._FINAL_DAY_PSIONIC_SOURCE_KEY] = self._FINAL_DAY_PSIONIC_PARASITISM_RULE_NAME
        tyr_root.special_rules = tyr_sr

        return {
            "action": "mark",
            "synapse_unit_id": str(get_entity_id(synapse_root) or ""),
            "gsc_unit_id": str(get_entity_id(gsc_root) or ""),
            "tyranids_unit_id": str(get_entity_id(tyr_root) or ""),
            "mortal_wounds": int(mortal),
            "healed_wounds": int(healed),
            "healed_model_id": healed_model_id,
            "source": self._FINAL_DAY_PSIONIC_PARASITISM_RULE_NAME,
        }

    def final_day_psionic_parasitism_hit_bonus(self, attacker_model, *, game=None, weapon_profile=None) -> tuple[int, str]:
        del weapon_profile  # Unused; parity with other hooks.
        if not self.is_final_day():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        attacker_root = self._attached_root(getattr(attacker_model, "parent_unit", None))
        if attacker_root is None:
            return 0, ""
        if not self._unit_in_army(attacker_root):
            return 0, ""
        if not self._unit_is_tyranids(attacker_root):
            return 0, ""
        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(self._FINAL_DAY_PSIONIC_ACTIVE_KEY)):
            return 0, ""
        if game is not None:
            effect_owner = str(sr.get(self._FINAL_DAY_PSIONIC_OWNER_KEY, "") or "")
            try:
                effect_turn = int(sr.get(self._FINAL_DAY_PSIONIC_TURN_KEY, 0) or 0)
            except (TypeError, ValueError):
                effect_turn = 0
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            current_player = getattr(game, "get_current_player", lambda: None)()
            current_owner = str(getattr(current_player, "id", "") or "")
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
            if (
                phase_name == "MOVEMENT_PHASE"
                and effect_owner
                and current_owner == effect_owner
                and current_turn
                and effect_turn
                and current_turn > effect_turn
            ):
                return 0, ""
        bonus = int(sr.get(self._FINAL_DAY_PSIONIC_BONUS_KEY, 1) or 1)
        if bonus <= 0:
            return 0, ""
        source_name = str(sr.get(self._FINAL_DAY_PSIONIC_SOURCE_KEY, "") or self._FINAL_DAY_PSIONIC_PARASITISM_RULE_NAME)
        return int(bonus), source_name

    def final_day_catalyst_hit_bonus(self, attacker_model, target_unit, *, game=None, weapon_profile=None) -> tuple[int, str]:
        del weapon_profile  # Unused; parity with other hooks.
        if not self.is_final_day():
            return 0, ""
        if attacker_model is None or target_unit is None or game is None:
            return 0, ""
        game_map = getattr(game, "map", None)
        if game_map is None:
            return 0, ""
        attacker_root = self._attached_root(getattr(attacker_model, "parent_unit", None))
        target_root = self._attached_root(target_unit)
        if attacker_root is None or target_root is None:
            return 0, ""
        if not self._unit_in_army(attacker_root):
            return 0, ""
        if not self._unit_is_genestealer_cults(attacker_root):
            return 0, ""
        if self._unit_is_tyranids(attacker_root):
            return 0, ""
        if self._final_day_target_within_range_of_friendly_tyranids(
            target_root,
            range_in=6.0,
            game=game,
            game_map=game_map,
        ):
            return 1, self._FINAL_DAY_CATALYST_RULE_NAME
        return 0, ""

    def final_day_inhuman_integration_sustained_hits_value(
        self,
        attacker_model,
        target_unit,
        *,
        game=None,
        game_map=None,
        weapon_profile=None,
    ) -> tuple[int, str]:
        del weapon_profile  # Unused; parity with other keyword hooks.
        if not self.is_final_day():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        attacker_root = self._attached_root(getattr(attacker_model, "parent_unit", None))
        target_root = self._attached_root(target_unit)
        if attacker_root is None or target_root is None:
            return 0, ""
        if not self._unit_in_army(attacker_root):
            return 0, ""
        if not self._unit_is_genestealer_cults(attacker_root):
            return 0, ""
        if self._unit_is_tyranids(attacker_root):
            return 0, ""
        source_record = self._final_day_inhuman_integration_record(attacker_root)
        if source_record is None:
            return 0, ""
        _source_root, _source_member, source_sr, _bearer = source_record
        try:
            range_in = float(source_sr.get(self._FINAL_DAY_INHUMAN_INTEGRATION_RANGE_KEY, 6.0) or 6.0)
        except (TypeError, ValueError):
            range_in = 6.0
        if not self._final_day_target_within_range_of_friendly_tyranids(
            target_root,
            range_in=range_in,
            game=game,
            game_map=game_map,
        ):
            return 0, ""
        try:
            sustained_hits_value = int(source_sr.get(self._FINAL_DAY_INHUMAN_INTEGRATION_VALUE_KEY, 1) or 1)
        except (TypeError, ValueError):
            sustained_hits_value = 1
        if sustained_hits_value <= 0:
            return 0, ""
        source_name = str(
            source_sr.get(self._FINAL_DAY_INHUMAN_INTEGRATION_SOURCE_KEY, "") or self._FINAL_DAY_INHUMAN_INTEGRATION_RULE_NAME
        ).strip() or self._FINAL_DAY_INHUMAN_INTEGRATION_RULE_NAME
        return int(sustained_hits_value), source_name

    def _clear_final_day_psionic_bonus(self, unit) -> None:
        root = self._attached_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            self._FINAL_DAY_PSIONIC_ACTIVE_KEY,
            self._FINAL_DAY_PSIONIC_BONUS_KEY,
            self._FINAL_DAY_PSIONIC_OWNER_KEY,
            self._FINAL_DAY_PSIONIC_TURN_KEY,
            self._FINAL_DAY_PSIONIC_SOURCE_KEY,
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _brood_brothers_forbidden_unit_reasons(self, unit) -> list[str]:
        if unit is None:
            return []
        reasons: list[str] = []
        if bool(getattr(unit, "is_epic_hero", False)):
            reasons.append("EPIC HERO")
        for keyword in self._BROOD_BROTHERS_FORBIDDEN_KEYWORDS:
            if self._unit_has_keyword(unit, keyword):
                reasons.append(keyword)
        name_token = self._name_token(getattr(unit, "name", ""))
        for token in self._BROOD_BROTHERS_FORBIDDEN_NAME_TOKENS:
            if token and token in name_token:
                reasons.append(token.upper())
        unique: list[str] = []
        seen: set[str] = set()
        for reason in reasons:
            key = str(reason or "").strip().upper()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(key)
        return unique

    def _final_day_forbidden_tyranid_reasons(self, unit) -> list[str]:
        if unit is None:
            return []
        reasons: list[str] = []
        if not self._unit_has_keyword(unit, self._FINAL_DAY_TYRANID_REQUIRED_KEYWORD):
            reasons.append(f"MISSING {self._FINAL_DAY_TYRANID_REQUIRED_KEYWORD}")
        for keyword in self._FINAL_DAY_TYRANID_FORBIDDEN_KEYWORDS:
            if self._unit_has_keyword(unit, keyword):
                reasons.append(keyword)
        name_token = self._name_token(getattr(unit, "name", ""))
        if "broodlord" in name_token:
            reasons.append("BROODLORD")
        if "genestealers" in name_token:
            reasons.append("GENESTEALERS")
        unique: list[str] = []
        seen: set[str] = set()
        for reason in reasons:
            key = str(reason or "").strip().upper()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(key)
        return unique

    def apply_brood_brothers_voice_of_command_loss(self) -> None:
        if not self.is_brood_brother_auxilia():
            return
        for root in self._iter_unit_roots():
            if not self._unit_is_astra_militarum(root):
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr[self._BROOD_BROTHERS_VOICE_OF_COMMAND_LOST_KEY] = True
            for key in (
                "voice_of_command_order_key",
                "voice_of_command_order_owner",
                "voice_of_command_order_source",
                "voice_of_command_take_cover_cap",
            ):
                sr.pop(key, None)
            root.special_rules = sr
            remove_modifiers = getattr(root, "remove_characteristic_modifiers_by_source", None)
            if callable(remove_modifiers):
                remove_modifiers("voice_of_command:")

    def brood_brothers_voice_of_command_lost_for_unit(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        return bool(isinstance(sr, dict) and sr.get(self._BROOD_BROTHERS_VOICE_OF_COMMAND_LOST_KEY))

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        army = self.army
        if army is None:
            return errors

        if self.is_brood_brother_auxilia():
            self.apply_brood_brothers_voice_of_command_loss()

            cap, size_label = self._brood_brothers_points_cap(int(getattr(army, "points_limit", 0) or 0))
            brood_brothers_points = 0
            for unit in self._iter_unit_roots():
                if not self._unit_is_astra_militarum(unit):
                    continue
                brood_brothers_points += self._unit_points(unit)
                forbidden = self._brood_brothers_forbidden_unit_reasons(unit)
                if not forbidden:
                    continue
                name = str(getattr(unit, "name", "") or "Unit").strip() or "Unit"
                errors.append(
                    "Brood Brother Auxilia: ASTRA MILITARUM unit "
                    f"'{name}' is not allowed ({', '.join(forbidden)})."
                )

            if int(brood_brothers_points) > int(cap):
                errors.append(
                    "Brood Brother Auxilia: combined ASTRA MILITARUM points "
                    f"({int(brood_brothers_points)}) exceed the {size_label} cap of {int(cap)}."
                )

            warlord = getattr(army, "warlord", None)
            if warlord is None:
                for unit in self._iter_unit_roots():
                    if bool(getattr(unit, "is_warlord", False)):
                        warlord = unit
                        break
            warlord_root = self._attached_root(warlord)
            if warlord_root is not None and not self._unit_is_genestealer_cults(warlord_root):
                errors.append(
                    "Brood Brother Auxilia: a GENESTEALER CULTS model from your army must be your WARLORD."
                )

        if self.is_final_day():
            cap, size_label = self._brood_brothers_points_cap(int(getattr(army, "points_limit", 0) or 0))
            tyranids_points = 0
            for unit in self._iter_unit_roots():
                if not self._unit_is_tyranids(unit):
                    continue
                tyranids_points += self._unit_points(unit)
                forbidden = self._final_day_forbidden_tyranid_reasons(unit)
                if not forbidden:
                    continue
                name = str(getattr(unit, "name", "") or "Unit").strip() or "Unit"
                errors.append(
                    "Final Day: TYRANIDS unit "
                    f"'{name}' is not allowed ({', '.join(forbidden)})."
                )

            if int(tyranids_points) > int(cap):
                errors.append(
                    "Final Day: combined TYRANIDS points "
                    f"({int(tyranids_points)}) exceed the {size_label} cap of {int(cap)}."
                )

            warlord = getattr(army, "warlord", None)
            if warlord is None:
                for unit in self._iter_unit_roots():
                    if bool(getattr(unit, "is_warlord", False)):
                        warlord = unit
                        break
            warlord_root = self._attached_root(warlord)
            if warlord_root is not None and self._unit_is_tyranids(warlord_root):
                errors.append("Final Day: no TYRANIDS models from your army can be your WARLORD.")
        return errors

    def _is_hypermorphic_fury_eligible_unit(self, unit) -> bool:
        if not self.is_biosanctic_broodsurge():
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_genestealer_cults(root):
            return False
        names = self._unit_name_tokens(root)
        for token in self._HYPERMORPHIC_FURY_ELIGIBLE_NAME_TOKENS:
            if token in names:
                return True
        return False

    def is_biosanctic_stratagem_eligible_unit(self, unit) -> bool:
        return self._is_hypermorphic_fury_eligible_unit(unit)

    def hypermorphic_fury_charge_roll_bonus(self, unit, *, target_units=None, game=None) -> tuple[int, str]:
        del target_units  # Unused; present for parity with other detachment manager hooks.
        del game  # Unused; present for parity with other detachment manager hooks.
        if not self._is_hypermorphic_fury_eligible_unit(unit):
            return 0, ""
        return 1, self._HYPERMORPHIC_FURY_RULE_NAME

    def hypermorphic_fury_melee_attacks_bonus(self, unit, *, game=None) -> tuple[int, str]:
        if not self._is_hypermorphic_fury_eligible_unit(unit):
            return 0, ""
        root = self._attached_root(unit)
        if root is None:
            return 0, ""
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "charged_this_round", False)):
            return 0, ""
        if game is not None:
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            if phase_name and phase_name != "FIGHT_PHASE":
                return 0, ""
        return 1, self._HYPERMORPHIC_FURY_RULE_NAME

    def biosanctic_stimulated_bio_surge_charge_roll_bonus(self, unit, *, target_units=None, game=None) -> tuple[int, str]:
        root = self._attached_root(unit)
        if root is None or not self.is_biosanctic_broodsurge():
            return 0, ""
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(self._STIMULATED_BIO_SURGE_ACTIVE_KEY)):
            return 0, ""
        if not self._is_phase_owner_turn_active(
            sr,
            game=game,
            owner_key=self._STIMULATED_BIO_SURGE_OWNER_KEY,
            turn_key=self._STIMULATED_BIO_SURGE_TURN_KEY,
            phase_key=self._STIMULATED_BIO_SURGE_PHASE_KEY,
        ):
            return 0, ""
        if target_units is None:
            return 0, ""
        targets = list(target_units) if isinstance(target_units, (list, tuple, set)) else [target_units]
        target_roots = [self._attached_root(target) for target in list(targets or []) if self._attached_root(target) is not None]
        if not target_roots:
            return 0, ""

        closest_ids = self._stimulated_bio_surge_closest_eligible_target_ids(root, game=game)
        if closest_ids and not any(str(get_entity_id(target) or "") in closest_ids for target in target_roots):
            return 0, ""
        try:
            bonus_per_target = int(sr.get(self._STIMULATED_BIO_SURGE_PER_TARGET_KEY, 1) or 1)
        except (TypeError, ValueError):
            bonus_per_target = 1
        try:
            max_bonus = int(sr.get(self._STIMULATED_BIO_SURGE_MAX_KEY, 3) or 3)
        except (TypeError, ValueError):
            max_bonus = 3
        bonus = min(max(0, int(max_bonus)), max(0, int(bonus_per_target)) * len(target_roots))
        if bonus <= 0:
            return 0, ""
        source = str(sr.get(self._STIMULATED_BIO_SURGE_SOURCE_KEY, "") or self._STIMULATED_BIO_SURGE_RULE_NAME).strip()
        return int(bonus), source or self._STIMULATED_BIO_SURGE_RULE_NAME

    def _stimulated_bio_surge_closest_eligible_target_ids(self, unit, *, game=None) -> set[str]:
        root = self._attached_root(unit)
        if root is None or game is None:
            return set()
        game_map = self._resolve_game_map(game=game)
        distance_fn = getattr(game_map, "get_distance_between_units", None) if game_map is not None else None
        if not callable(distance_fn):
            return set()
        player = getattr(self.army, "player", None) if self.army is not None else None
        if player is None or not callable(getattr(game, "get_enemy_units", None)):
            return set()
        can_declare_charge_against = getattr(root, "can_declare_charge_against", None)
        if not callable(can_declare_charge_against):
            return set()

        closest_ids: set[str] = set()
        closest_distance: float | None = None
        seen: set[str] = set()
        for enemy in list(game.get_enemy_units(player) or []):
            enemy_root = self._attached_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = str(get_entity_id(enemy_root) or "")
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if not self._unit_is_on_battlefield(enemy_root):
                continue
            try:
                if not bool(can_declare_charge_against(enemy_root, game, out_of_turn=False)):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            try:
                distance = float(distance_fn(root, enemy_root))
            except (AttributeError, TypeError, ValueError):
                continue
            if closest_distance is None or distance < (closest_distance - 1e-6):
                closest_distance = distance
                closest_ids = {enemy_id} if enemy_id else set()
                continue
            if closest_distance is not None and abs(distance - closest_distance) <= 1e-6 and enemy_id:
                closest_ids.add(enemy_id)
        return closest_ids

    @staticmethod
    def _biosanctic_effect_matches_phase_and_turn(
        sr: dict,
        *,
        active_key: str,
        phase_key: str,
        turn_key: str,
        phase_name: str,
        current_turn: int,
    ) -> bool:
        if not isinstance(sr, dict) or not bool(sr.get(active_key)):
            return False
        expected_phase = str(sr.get(phase_key, "") or "").strip().upper()
        if expected_phase and phase_name and expected_phase != phase_name:
            return False
        try:
            effect_turn = int(sr.get(turn_key, 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        if current_turn and effect_turn and current_turn != effect_turn:
            return False
        return True

    @staticmethod
    def _clear_special_rule_keys(unit, keys: tuple[str, ...]) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return
        changed = False
        for key in keys:
            if key in sr:
                sr.pop(key, None)
                changed = True
        if changed:
            unit.special_rules = sr

    def _clear_temporary_weapon_keyword_effects(
        self,
        unit,
        *,
        sr_key: str,
        owner_id: str | None = None,
    ) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return

        entries_raw = list(sr.get(sr_key, []) or [])
        if not entries_raw:
            return

        model_by_id = {
            str(get_entity_id(model) or ""): model
            for model in self._iter_attached_models(unit)
        }

        remaining: list[dict] = []
        owner_key = str(owner_id or "")
        for entry in entries_raw:
            if not isinstance(entry, dict):
                continue
            entry_owner = str(entry.get("owner_id", "") or "")
            if owner_key and entry_owner != owner_key:
                remaining.append(entry)
                continue

            for model_key in list(entry.get("model_effect_keys", []) or []):
                if not isinstance(model_key, dict):
                    continue
                model_id = str(model_key.get("model_id", "") or "")
                effect_key = str(model_key.get("effect_key", "") or "").strip().lower()
                if not model_id or not effect_key:
                    continue
                model = model_by_id.get(model_id)
                if model is None:
                    continue
                effects = getattr(model, "_temporary_effects", None)
                if isinstance(effects, dict):
                    effects.pop(effect_key, None)

        if remaining:
            sr[sr_key] = remaining
        else:
            sr.pop(sr_key, None)
        unit.special_rules = sr

    def _clear_a_perfect_ambush_effects(self, unit, *, owner_id: str | None = None) -> None:
        self._clear_temporary_weapon_keyword_effects(
            unit,
            sr_key=self._A_PERFECT_AMBUSH_SR_KEY,
            owner_id=owner_id,
        )

    def _clear_a_chink_in_their_armour_effects(self, unit, *, owner_id: str | None = None) -> None:
        self._clear_temporary_weapon_keyword_effects(
            unit,
            sr_key=self._A_CHINK_SR_KEY,
            owner_id=owner_id,
        )

    def _has_host_of_ascension_enhancement(self, unit, *, enhancement_id: str, name_key: str) -> bool:
        target_id = str(enhancement_id or "").strip()
        target_name_key = str(name_key or "").strip().lower()
        try:
            members = list(unit.get_attached_unit_members() or [])
        except Exception:
            members = [unit]
        if not members:
            members = [unit]
        for member in members:
            enhancement = getattr(member, "enhancement", None)
            if enhancement is None:
                continue
            enh_id = str(getattr(enhancement, "id", "") or "").strip()
            if target_id and enh_id == target_id:
                return True
            enh_name = str(getattr(enhancement, "name", "") or "").strip().lower()
            enh_name = re.sub(r"[^a-z0-9]+", "", enh_name)
            if target_name_key and enh_name == target_name_key:
                return True
        return False

    def _apply_host_of_ascension_reinforcement_weapon_keywords(
        self,
        unit,
        *,
        game,
        owner_id: str,
        source_name: str,
        sr_key: str,
        key_prefix: str,
        keywords: tuple[str, ...],
        attack_type: str = "any",
    ) -> None:
        self._clear_temporary_weapon_keyword_effects(unit, sr_key=sr_key)

        model_effect_keys: list[dict] = []
        for model in self._iter_attached_models(unit):
            alive = getattr(model, "is_alive", True)
            if callable(alive):
                alive = alive()
            if not bool(alive):
                continue
            set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
            if not callable(set_keywords):
                continue
            model_id = str(get_entity_id(model) or "")
            if not model_id:
                continue
            weapon_names = self._model_weapon_names(model, attack_type=attack_type)
            for idx, weapon_name in enumerate(weapon_names):
                effect_key = f"{key_prefix}:{model_id}:{idx}"
                set_keywords(
                    key=effect_key,
                    weapon_name=weapon_name,
                    keywords=list(keywords),
                    source=source_name,
                    expires_phase="",
                    attack_type=str(attack_type or "any"),
                )
                model_effect_keys.append(
                    {
                        "model_id": model_id,
                        "effect_key": effect_key,
                    }
                )

        if not model_effect_keys:
            return

        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        entries = [
            entry
            for entry in list(sr.get(sr_key, []) or [])
            if isinstance(entry, dict)
        ]
        effect_entry: dict = {
            "owner_id": owner_id,
            "source": source_name,
            "model_effect_keys": model_effect_keys,
        }
        if game is not None:
            effect_entry["battle_round"] = int(getattr(game, "turn", 0) or 0)
        entries.append(effect_entry)
        sr[sr_key] = entries
        unit.special_rules = sr

    def on_unit_set_up(self, *, unit=None, game=None, set_up_as_reinforcements: bool = False) -> None:
        if not self.is_host_of_ascension():
            return
        if not bool(set_up_as_reinforcements):
            return

        root = self._attached_root(unit)
        if root is None:
            return
        if not self._unit_in_army(root):
            return
        if not self._unit_is_genestealer_cults(root):
            return

        army = self.army
        if army is None:
            return
        player = getattr(army, "player", None)
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return

        self._apply_host_of_ascension_reinforcement_weapon_keywords(
            root,
            game=game,
            owner_id=owner_id,
            source_name=self._A_PERFECT_AMBUSH_RULE_NAME,
            sr_key=self._A_PERFECT_AMBUSH_SR_KEY,
            key_prefix=self._A_PERFECT_AMBUSH_KEY_PREFIX,
            keywords=self._A_PERFECT_AMBUSH_KEYWORDS,
            attack_type="any",
        )

        if self._has_host_of_ascension_enhancement(
            root,
            enhancement_id=self._A_CHINK_ENHANCEMENT_ID,
            name_key=self._A_CHINK_NAME_KEY,
        ):
            self._apply_host_of_ascension_reinforcement_weapon_keywords(
                root,
                game=game,
                owner_id=owner_id,
                source_name=self._A_CHINK_RULE_NAME,
                sr_key=self._A_CHINK_SR_KEY,
                key_prefix=self._A_CHINK_KEY_PREFIX,
                keywords=self._A_CHINK_KEYWORDS,
                attack_type="ranged",
            )

    def cleanup_on_phase_start(self, phase, active_player) -> None:
        phase_name = str(getattr(phase, "name", phase) or "").strip().upper()
        if not self.is_final_day() or phase_name != "MOVEMENT_PHASE":
            return
        owner_id = str(getattr(active_player, "id", "") or "")
        game = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        for root in self._iter_unit_roots():
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(self._FINAL_DAY_PSIONIC_ACTIVE_KEY)):
                continue
            if owner_id and str(sr.get(self._FINAL_DAY_PSIONIC_OWNER_KEY, "") or "") not in ("", owner_id):
                continue
            try:
                effect_turn = int(sr.get(self._FINAL_DAY_PSIONIC_TURN_KEY, 0) or 0)
            except (TypeError, ValueError):
                effect_turn = 0
            if current_turn and effect_turn and current_turn <= effect_turn:
                continue
            self._clear_final_day_psionic_bonus(root)

    def cleanup_on_phase_end(self, phase, active_player) -> None:
        phase_name = str(getattr(phase, "name", phase) or "").strip().upper()
        game = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
        current_turn = self._current_turn(game=game)
        if self.is_host_of_ascension() and phase_name == "FIGHT_PHASE":
            owner_id = str(getattr(active_player, "id", "") or "")
            if owner_id:
                for root in self._iter_unit_roots():
                    self._clear_a_perfect_ambush_effects(root, owner_id=owner_id)
                    self._clear_a_chink_in_their_armour_effects(root, owner_id=owner_id)

        if self.is_brood_brother_auxilia() and phase_name == "SHOOTING_PHASE":
            owner_id = str(getattr(active_player, "id", "") or "")
            for root in self._iter_unit_roots():
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict) or not bool(sr.get(self._INTEGRATED_TACTICS_SOURCE_ACTIVE_KEY)):
                    continue
                if owner_id and str(sr.get(self._INTEGRATED_TACTICS_SOURCE_OWNER_KEY, "") or "") not in ("", owner_id):
                    continue
                try:
                    effect_turn = int(sr.get(self._INTEGRATED_TACTICS_SOURCE_TURN_KEY, 0) or 0)
                except (TypeError, ValueError):
                    effect_turn = 0
                if current_turn and effect_turn and effect_turn != current_turn:
                    continue
                self._clear_integrated_tactics_source_lock(root)

            owner_player = getattr(self.army, "player", None) if self.army is not None else None
            if game is not None and owner_player is not None and callable(getattr(game, "get_enemy_units", None)):
                for enemy in list(game.get_enemy_units(owner_player) or []):
                    target_root = self._attached_root(enemy)
                    target_sr = getattr(target_root, "special_rules", None)
                    if not isinstance(target_sr, dict) or not bool(target_sr.get(self._INTEGRATED_TACTICS_TARGET_ACTIVE_KEY)):
                        continue
                    if owner_id and str(target_sr.get(self._INTEGRATED_TACTICS_TARGET_OWNER_KEY, "") or "") not in ("", owner_id):
                        continue
                    try:
                        effect_turn = int(target_sr.get(self._INTEGRATED_TACTICS_TARGET_TURN_KEY, 0) or 0)
                    except (TypeError, ValueError):
                        effect_turn = 0
                    if current_turn and effect_turn and effect_turn != current_turn:
                        continue
                    self._clear_integrated_tactics_target_mark(target_root)

        if self.is_biosanctic_broodsurge():
            for root in self._iter_unit_roots():
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if phase_name == "SHOOTING_PHASE" and self._biosanctic_effect_matches_phase_and_turn(
                    sr,
                    active_key=self._BIO_HORROR_ACTIVE_KEY,
                    phase_key=self._BIO_HORROR_PHASE_KEY,
                    turn_key=self._BIO_HORROR_TURN_KEY,
                    phase_name=phase_name,
                    current_turn=current_turn,
                ):
                    self._clear_special_rule_keys(
                        root,
                        (
                            self._BIO_HORROR_ACTIVE_KEY,
                            self._BIO_HORROR_OWNER_KEY,
                            self._BIO_HORROR_TURN_KEY,
                            self._BIO_HORROR_PHASE_KEY,
                            self._BIO_HORROR_SOURCE_KEY,
                        ),
                    )
                if phase_name == "FIGHT_PHASE" and self._biosanctic_effect_matches_phase_and_turn(
                    sr,
                    active_key=self._GENE_TWISTED_MUSCLE_ACTIVE_KEY,
                    phase_key=self._GENE_TWISTED_MUSCLE_PHASE_KEY,
                    turn_key=self._GENE_TWISTED_MUSCLE_TURN_KEY,
                    phase_name=phase_name,
                    current_turn=current_turn,
                ):
                    self._clear_special_rule_keys(
                        root,
                        (
                            self._GENE_TWISTED_MUSCLE_ACTIVE_KEY,
                            self._GENE_TWISTED_MUSCLE_BONUS_KEY,
                            self._GENE_TWISTED_MUSCLE_OWNER_KEY,
                            self._GENE_TWISTED_MUSCLE_TURN_KEY,
                            self._GENE_TWISTED_MUSCLE_PHASE_KEY,
                            self._GENE_TWISTED_MUSCLE_SOURCE_KEY,
                        ),
                    )
                if phase_name == "FIGHT_PHASE" and self._biosanctic_effect_matches_phase_and_turn(
                    sr,
                    active_key=self._HYPER_METABOLIC_VIGOUR_ACTIVE_KEY,
                    phase_key=self._HYPER_METABOLIC_VIGOUR_PHASE_KEY,
                    turn_key=self._HYPER_METABOLIC_VIGOUR_TURN_KEY,
                    phase_name=phase_name,
                    current_turn=current_turn,
                ):
                    self._clear_special_rule_keys(
                        root,
                        (
                            self._HYPER_METABOLIC_VIGOUR_ACTIVE_KEY,
                            self._HYPER_METABOLIC_VIGOUR_OWNER_KEY,
                            self._HYPER_METABOLIC_VIGOUR_TURN_KEY,
                            self._HYPER_METABOLIC_VIGOUR_PHASE_KEY,
                            self._HYPER_METABOLIC_VIGOUR_SOURCE_KEY,
                            "stratagem_pile_in_distance_override",
                            "stratagem_pile_in_expires_phase",
                            "stratagem_consolidate_distance_override",
                            "stratagem_consolidate_expires_phase",
                            "stratagem_choreographer_of_war_source",
                        ),
                    )
                if phase_name == "CHARGE_PHASE" and self._biosanctic_effect_matches_phase_and_turn(
                    sr,
                    active_key=self._STIMULATED_BIO_SURGE_ACTIVE_KEY,
                    phase_key=self._STIMULATED_BIO_SURGE_PHASE_KEY,
                    turn_key=self._STIMULATED_BIO_SURGE_TURN_KEY,
                    phase_name=phase_name,
                    current_turn=current_turn,
                ):
                    self._clear_special_rule_keys(
                        root,
                        (
                            self._STIMULATED_BIO_SURGE_ACTIVE_KEY,
                            self._STIMULATED_BIO_SURGE_OWNER_KEY,
                            self._STIMULATED_BIO_SURGE_TURN_KEY,
                            self._STIMULATED_BIO_SURGE_PHASE_KEY,
                            self._STIMULATED_BIO_SURGE_SOURCE_KEY,
                            self._STIMULATED_BIO_SURGE_PER_TARGET_KEY,
                            self._STIMULATED_BIO_SURGE_MAX_KEY,
                        ),
                    )
