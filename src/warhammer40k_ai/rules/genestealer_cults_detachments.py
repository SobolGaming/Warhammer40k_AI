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
        if not self.is_brood_brother_auxilia():
            return errors
        army = self.army
        if army is None:
            return errors

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

    def cleanup_on_phase_end(self, phase, active_player) -> None:
        phase_name = str(getattr(phase, "name", phase) or "").strip().upper()
        if self.is_host_of_ascension() and phase_name == "FIGHT_PHASE":
            owner_id = str(getattr(active_player, "id", "") or "")
            if owner_id:
                for root in self._iter_unit_roots():
                    self._clear_a_perfect_ambush_effects(root, owner_id=owner_id)
                    self._clear_a_chink_in_their_armour_effects(root, owner_id=owner_id)

        if self.is_brood_brother_auxilia() and phase_name == "SHOOTING_PHASE":
            owner_id = str(getattr(active_player, "id", "") or "")
            game = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0

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
