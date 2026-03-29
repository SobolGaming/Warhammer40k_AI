from __future__ import annotations

import re
import unicodedata

from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class LeaguesOfVotannDetachmentManager(DetachmentManagerBase):
    faction_id = "LOV"

    _METHODICAL_AP_UNIT_TOKENS = (
        "kahl",
        "uthar the destined",
        "einhyr hearthguard",
    )
    _MOBILE_SENSOR_RELAYS_SOURCE = "Mobile Sensor Relays: Firebase Control"
    _OPTIMAL_APPLICATION_SOURCE = "Optimal Application"

    def is_brandfast_oathband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Brandfast Oathband")

    def is_delve_assault_shift(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return (
            self._detachment_matches_normalized("Dêlve Assault Shift")
            or self._detachment_matches_normalized("Delve Assault Shift")
        )

    def is_hearthband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hearthband")

    def is_hearthfyre_arsenal(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hearthfyre Arsenal")

    def is_mercenary_oathband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Mercenary Oathband")

    def is_persecution_prospect(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Persecution Prospect")

    def is_needgaard_oathband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return (
            self._detachment_matches_normalized("Needgaârd Oathband")
            or self._detachment_matches_normalized("Needgaard Oathband")
        )

    def ruthless_reinvestment_overrides_mode_updates(self) -> bool:
        return self.is_mercenary_oathband()

    def _normalize_text(self, text: str) -> str:
        t = unicodedata.normalize("NFKD", str(text or ""))
        t = t.encode("ascii", "ignore").decode("ascii")
        t = re.sub(r"[^a-z0-9 ]+", " ", t.lower())
        return re.sub(r"\s+", " ", t).strip()

    def _detachment_matches_normalized(self, detachment_name: str) -> bool:
        det = self._normalize_text(self._get_detachment_type())
        target = self._normalize_text(detachment_name)
        if not det or not target:
            return False
        if det == target:
            return True
        if det.endswith("s") and det[:-1] == target:
            return True
        if target.endswith("s") and target[:-1] == det:
            return True
        return det in target or target in det

    @staticmethod
    def _attached_root(unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _entity_id(entity) -> str:
        try:
            return str(get_entity_id(entity) or "")
        except ValueError:
            return ""

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    @staticmethod
    def _unit_is_on_battlefield(unit) -> bool:
        if unit is None:
            return False
        active_for_rules = getattr(unit, "is_active_for_rules", None)
        if callable(active_for_rules):
            return bool(active_for_rules())
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
            return False
        if bool(getattr(unit, "embarked_in", None)):
            return False
        return True

    def _iter_unique_army_roots(self) -> list:
        if self.army is None:
            return []
        roots = []
        seen = set()
        for idx, unit in enumerate(list(getattr(self.army, "units", []) or [])):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root) or f"idx:{idx}"
            if root_id in seen:
                continue
            seen.add(root_id)
            roots.append(root)
        return roots

    def _unit_has_role_keyword(self, unit, keyword: str) -> bool:
        for member in self._attached_unit_members(unit):
            if self._unit_has_keyword(member, keyword):
                return True
        return False

    def _unit_is_transport(self, unit) -> bool:
        return bool(unit is not None and self._unit_has_role_keyword(unit, "TRANSPORT"))

    def _unit_is_infantry(self, unit) -> bool:
        return bool(unit is not None and self._unit_has_role_keyword(unit, "INFANTRY"))

    def _unit_is_monster_or_vehicle(self, unit) -> bool:
        if unit is None:
            return False
        return bool(
            self._unit_has_role_keyword(unit, "MONSTER")
            or self._unit_has_role_keyword(unit, "VEHICLE")
        )

    def _unit_matches_iron_master_or_memnyr_keywords(self, unit) -> bool:
        if unit is None:
            return False
        texts = [getattr(unit, "name", "")]
        texts += list(getattr(unit, "keywords", []) or [])
        texts += list(getattr(unit, "faction_keywords", []) or [])
        for raw in texts:
            norm = self._normalize_text(raw)
            if "brokhyr iron master" in norm or "brokhyr ironmaster" in norm:
                return True
            if "iron master" in norm and "brokhyr" in norm:
                return True
            if "memnyr strategist" in norm:
                return True
        return False

    def _unit_matches_optimal_application_shooter_keywords(self, unit) -> bool:
        if unit is None:
            return False
        texts = [getattr(unit, "name", "")]
        texts += list(getattr(unit, "keywords", []) or [])
        texts += list(getattr(unit, "faction_keywords", []) or [])
        for raw in texts:
            norm = self._normalize_text(raw)
            if "brokhyr" in norm:
                return True
            if "ironkin steeljacks" in norm:
                return True
            if "ironkin" in norm and "steeljacks" in norm:
                return True
            if "arkanyst evaluator" in norm:
                return True
        return False

    def _unit_matches_cthonian_beserks_keywords(self, unit) -> bool:
        if unit is None:
            return False
        texts = [getattr(unit, "name", "")]
        texts += list(getattr(unit, "keywords", []) or [])
        texts += list(getattr(unit, "faction_keywords", []) or [])
        for raw in texts:
            norm = self._normalize_text(raw)
            if "cthonian beserks" in norm:
                return True
            if "cthonian" in norm and ("beserks" in norm or "beserk" in norm):
                return True
        return False

    def _unit_is_cthonian_beserks(self, unit) -> bool:
        if unit is None:
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if self._unit_matches_cthonian_beserks_keywords(root):
            return True
        for member in self._attached_unit_members(root):
            if self._unit_matches_cthonian_beserks_keywords(member):
                return True
        return False

    @staticmethod
    def _weapon_is_ranged(weapon_profile) -> bool:
        if weapon_profile is None:
            return False
        parent = getattr(weapon_profile, "parent_wargear", None)
        return bool(parent is not None and callable(getattr(parent, "is_ranged", None)) and parent.is_ranged())

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        unit = getattr(model, "parent_unit", None)
        return self._unit_in_army(unit)

    def _unit_is_votann(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword_or_faction(unit, "LEAGUES OF VOTANN", faction_id=self.faction_id)

    def _model_is_votann(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        return self._unit_is_votann(unit)

    @staticmethod
    def _model_within_objective_marker(model, objective_point) -> bool:
        if model is None or objective_point is None:
            return False
        get_location = getattr(model, "get_location", None)
        if not callable(get_location):
            return False
        pos = get_location()
        if not pos:
            return False
        dx = float(pos[0]) - float(getattr(objective_point, "x", 0.0))
        dy = float(pos[1]) - float(getattr(objective_point, "y", 0.0))
        radius = float(getattr(objective_point, "control_radius", 0.0) or 0.0)
        get_radius = getattr(getattr(model, "model_base", None), "get_radius", None)
        base_radius = float(get_radius() if callable(get_radius) else 1.0)
        return (dx * dx + dy * dy) ** 0.5 <= (radius + base_radius)

    @staticmethod
    def _model_is_alive(model) -> bool:
        if model is None:
            return False
        is_alive = getattr(model, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        if is_alive is None:
            return True
        return bool(is_alive)

    def brandfast_unit_wholly_within_transport_range(self, unit, *, range_in: float = 6.0) -> bool:
        if unit is None:
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_votann(root):
            return False
        if not self._unit_is_on_battlefield(root):
            return False
        try:
            check_range = float(range_in)
        except (TypeError, ValueError):
            check_range = 6.0
        if check_range <= 0:
            return False

        from ..utility.aura_utils import unit_wholly_within_range_of_unit

        root_id = self._entity_id(root)
        for source in self._iter_unique_army_roots():
            if source is None:
                continue
            if not self._unit_is_on_battlefield(source):
                continue
            if not self._unit_is_votann(source):
                continue
            if not self._unit_is_transport(source):
                continue
            source_id = self._entity_id(source)
            if source_id and source_id == root_id:
                continue
            if unit_wholly_within_range_of_unit(source, root, check_range, use_attached_aggregate=True):
                return True
        return False

    def tactical_alchemy_unit_eligible(self, unit, *, game, player) -> bool:
        if not self.is_brandfast_oathband():
            return False
        if game is None or player is None:
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_votann(root):
            return False
        if not self._unit_is_on_battlefield(root):
            return False

        get_attached_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_attached_models() or []) if callable(get_attached_models) else list(getattr(root, "models", []) or [])
        active_models = [model for model in models if self._model_is_alive(model)]
        if not active_models:
            return False

        in_player_deployment = getattr(game, "_objective_in_player_deployment", None)
        for location in self._iter_objective_locations(game):
            update_control = getattr(location, "update_control", None)
            if callable(update_control):
                update_control(game)
            if getattr(location, "controlling_player", None) is not player:
                continue
            if callable(in_player_deployment) and bool(in_player_deployment(player, location)):
                continue
            for model in active_models:
                if self._model_within_objective_marker(model, location):
                    return True
        return False

    def mobile_sensor_relays_sustained_hits_value(self, model, weapon_profile=None, *, game_map=None) -> tuple[int, str]:
        del game_map
        if not self.is_brandfast_oathband():
            return 0, ""
        if model is None or not self._weapon_is_ranged(weapon_profile):
            return 0, ""
        if not self._model_in_army(model):
            return 0, ""
        if not self._model_is_votann(model):
            return 0, ""

        unit = getattr(model, "parent_unit", None)
        infantry_root = self._attached_root(unit)
        if infantry_root is None:
            return 0, ""
        if not self._unit_in_army(infantry_root):
            return 0, ""
        if not self._unit_is_on_battlefield(infantry_root):
            return 0, ""
        if not self._unit_is_votann(infantry_root):
            return 0, ""
        if not self._unit_is_infantry(infantry_root):
            return 0, ""
        if self.brandfast_unit_wholly_within_transport_range(infantry_root, range_in=6.0):
            return 1, self._MOBILE_SENSOR_RELAYS_SOURCE
        return 0, ""

    def trivarg_cyber_implant_sustained_hits_value(self, model, weapon_profile=None, *, game=None) -> tuple[int, str]:
        if not self.is_brandfast_oathband():
            return 0, ""
        if model is None or not self._weapon_is_ranged(weapon_profile):
            return 0, ""
        if not self._model_in_army(model):
            return 0, ""
        if not self._model_is_votann(model):
            return 0, ""

        unit = getattr(model, "parent_unit", None)
        root = self._attached_root(unit)
        if root is None:
            return 0, ""
        if not self._unit_in_army(root):
            return 0, ""
        if not self._unit_is_votann(root):
            return 0, ""
        if not self._unit_is_on_battlefield(root):
            return 0, ""

        game_obj = game
        if game_obj is None and self.army is not None:
            player = getattr(self.army, "player", None)
            game_obj = getattr(player, "game", None) if player is not None else None
        turn, owner_id = self._current_turn_context(game_obj)
        phase_name = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper()
        for member in self._attached_unit_members(root):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_trivarg_cyber_implant_active", False)):
                continue
            effect_owner = str(sr.get("enhancement_trivarg_cyber_implant_turn_owner", "") or "")
            if owner_id and effect_owner and effect_owner != owner_id:
                continue
            try:
                effect_turn = int(sr.get("enhancement_trivarg_cyber_implant_turn", 0) or 0)
            except (TypeError, ValueError):
                effect_turn = 0
            if turn and effect_turn and effect_turn != turn:
                continue
            effect_phase = str(sr.get("enhancement_trivarg_cyber_implant_expires_phase", "") or "").strip().upper()
            if phase_name and effect_phase and effect_phase != phase_name:
                continue
            try:
                sustained_hits_value = int(sr.get("enhancement_trivarg_cyber_implant_sustained_hits_value", 2) or 2)
            except (TypeError, ValueError):
                sustained_hits_value = 0
            if sustained_hits_value <= 0:
                continue
            source = str(sr.get("enhancement_trivarg_cyber_implant_source", "") or "Trivärg Cyber Implant").strip()
            return int(sustained_hits_value), source or "Trivärg Cyber Implant"
        return 0, ""

    def signature_restoration_repair_bonus(self, unit) -> int:
        if not self.is_brandfast_oathband():
            return 0
        root = self._attached_root(unit)
        if root is None:
            return 0
        if not self._unit_in_army(root):
            return 0
        if not self._unit_is_votann(root):
            return 0
        for member in self._attached_unit_members(root):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_signature_restoration", False)):
                continue
            get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            if bearer is not None and not self._model_is_alive(bearer):
                continue
            try:
                return max(0, int(sr.get("enhancement_signature_restoration_bonus", 1) or 1))
            except (TypeError, ValueError):
                return 0
        return 0

    def _current_turn_context(self, game) -> tuple[int, str]:
        if game is None:
            return 0, ""
        turn = int(getattr(game, "turn", 0) or 0)
        owner_id = ""
        get_current = getattr(game, "get_current_player", None)
        current_player = get_current() if callable(get_current) else None
        if current_player is not None:
            owner_id = str(getattr(current_player, "id", "") or "")
        return turn, owner_id

    def _player_is_current_turn_owner(self, game, player) -> bool:
        if game is None or player is None:
            return False
        get_current = getattr(game, "get_current_player", None)
        if callable(get_current):
            return get_current() is player
        return False

    def ruthless_reinvestment_toggle_used_this_turn(self, *, game, player=None) -> bool:
        if not self.is_mercenary_oathband() or game is None:
            return False
        turn, owner_id = self._current_turn_context(game)
        if player is not None and not owner_id:
            owner_id = str(getattr(player, "id", "") or "")
        if turn <= 0:
            return False
        try:
            last_turn = int(getattr(self, "_ruthless_reinvestment_last_toggle_turn", 0) or 0)
        except (TypeError, ValueError):
            last_turn = 0
        last_owner = str(getattr(self, "_ruthless_reinvestment_last_toggle_owner", "") or "")
        if last_turn != int(turn):
            return False
        if owner_id:
            return last_owner == owner_id
        return True

    def mark_ruthless_reinvestment_toggle_used(self, *, game, player=None) -> None:
        if game is None:
            return
        turn, owner_id = self._current_turn_context(game)
        if player is not None and not owner_id:
            owner_id = str(getattr(player, "id", "") or "")
        if turn <= 0:
            return
        self._ruthless_reinvestment_last_toggle_turn = int(turn)
        self._ruthless_reinvestment_last_toggle_owner = str(owner_id or "")

    def ruthless_reinvestment_can_toggle(self, *, game, player=None) -> bool:
        if not self.is_mercenary_oathband():
            return False
        if game is None or self.army is None:
            return False
        army_player = getattr(self.army, "player", None)
        if army_player is None:
            return False
        if player is not None and player is not army_player:
            return False
        if not self._player_is_current_turn_owner(game, army_player):
            return False
        return not self.ruthless_reinvestment_toggle_used_this_turn(game=game, player=army_player)

    def _iter_objective_locations(self, game) -> list:
        if game is None:
            return []
        game_map = getattr(game, "map", None)
        objectives = list(getattr(game_map, "objectives", []) or []) if game_map is not None else []
        locations = []
        for obj in objectives:
            location = getattr(obj, "location", obj)
            if location is None:
                continue
            if bool(getattr(location, "removed", False)):
                continue
            locations.append(location)
        return locations

    def _objective_has_iron_master_or_memnyr_model(self, objective_location) -> bool:
        for root in self._iter_unique_army_roots():
            if root is None:
                continue
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_on_battlefield(root):
                continue
            for member in self._attached_unit_members(root):
                if not self._unit_matches_iron_master_or_memnyr_keywords(member):
                    continue
                for model in list(getattr(member, "models", []) or []):
                    if not self._model_is_alive(model):
                        continue
                    if self._model_within_objective_marker(model, objective_location):
                        return True
        return False

    def optimal_application_command_phase_gain(self, *, game) -> int:
        if not self.is_hearthfyre_arsenal():
            return 0
        if self.army is None or game is None:
            return 0
        player = getattr(self.army, "player", None)
        if player is None:
            return 0
        if not self._player_is_current_turn_owner(game, player):
            return 0

        turn, owner_id = self._current_turn_context(game)
        if turn <= 0:
            return 0
        try:
            last_turn = int(getattr(self, "_optimal_application_last_gain_turn", 0) or 0)
        except (TypeError, ValueError):
            last_turn = 0
        last_owner = str(getattr(self, "_optimal_application_last_gain_owner", "") or "")
        if last_turn == turn and owner_id and last_owner == owner_id:
            return 0

        gained = 0
        in_player_deployment = getattr(game, "_objective_in_player_deployment", None)
        for location in self._iter_objective_locations(game):
            update_control = getattr(location, "update_control", None)
            if callable(update_control):
                update_control(game)
            if getattr(location, "controlling_player", None) is not player:
                continue
            if callable(in_player_deployment) and bool(in_player_deployment(player, location)):
                continue
            if not self._objective_has_iron_master_or_memnyr_model(location):
                continue
            gained += 1
            if gained >= 2:
                break

        if gained <= 0:
            return 0
        self._optimal_application_last_gain_turn = int(turn)
        self._optimal_application_last_gain_owner = str(owner_id or "")
        return int(gained)

    def optimal_application_shooting_unit_eligible(self, unit) -> bool:
        if not self.is_hearthfyre_arsenal():
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_votann(root):
            return False
        if not self._unit_is_on_battlefield(root):
            return False
        for member in self._attached_unit_members(root):
            if self._unit_matches_optimal_application_shooter_keywords(member):
                return True
        return False

    def persecution_prospect_shooting_unit_eligible(self, unit) -> bool:
        if not self.is_persecution_prospect():
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_votann(root):
            return False
        if not self._unit_is_on_battlefield(root):
            return False
        return True

    def persecution_prospect_target_eligible(self, source_unit, target_unit) -> bool:
        if not self.persecution_prospect_shooting_unit_eligible(source_unit):
            return False
        source_root = self._attached_root(source_unit)
        target_root = self._attached_root(target_unit)
        if source_root is None or target_root is None:
            return False
        if not self._unit_is_on_battlefield(target_root):
            return False
        source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
        target_army = target_root.get_parent_army() if hasattr(target_root, "get_parent_army") else None
        if source_army is None or target_army is None:
            return False
        if source_army is target_army:
            return False
        if self._unit_is_monster_or_vehicle(target_root):
            return False
        return True

    def fury_from_the_delve_grants_deep_strike(self, unit) -> bool:
        if not self.is_delve_assault_shift():
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_votann(root):
            return False
        return self._unit_is_cthonian_beserks(root)

    def apply_delve_assault_shift_battleline_keywords(self, unit=None) -> None:
        if not self.is_delve_assault_shift() or self.army is None:
            return
        units = [unit] if unit is not None else list(getattr(self.army, "units", []) or [])
        for entry in units:
            root = self._attached_root(entry)
            if root is None:
                continue
            if not self._unit_in_army(root):
                continue
            if not self._unit_is_cthonian_beserks(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            if any(str(k or "").strip().lower() == "battleline" for k in keywords):
                continue
            keywords.append("Battleline")
            root.keywords = keywords

    def _get_yield_points_manager(self):
        try:
            return getattr(self.army, "prioritised_efficiency", None) if self.army is not None else None
        except Exception:
            return None

    def martial_leverage_on_unit_destroyed(self, destroyed_unit, *, game=None) -> int:
        if not self.is_needgaard_oathband():
            return 0
        if destroyed_unit is None or self.army is None:
            return 0
        try:
            destroyed_army = destroyed_unit.get_parent_army()
        except Exception:
            destroyed_army = None
        if destroyed_army is None or destroyed_army is self.army:
            return 0
        mgr = self._get_yield_points_manager()
        if mgr is None:
            return 0
        return int(mgr.add_yield_points(1, game=game) or 0)

    def _attached_unit_members(self, unit) -> list:
        if unit is None:
            return []
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        members = root.get_attached_unit_members() if hasattr(root, "get_attached_unit_members") else None
        if not members:
            members = [root]
        return list(members)

    def _unit_is_methodical_ap_unit(self, unit) -> bool:
        if unit is None:
            return False
        tokens = self._METHODICAL_AP_UNIT_TOKENS
        for member in self._attached_unit_members(unit):
            name = self._normalize_text(getattr(member, "name", ""))
            if name and any(tok in name for tok in tokens):
                return True
        return False

    def _target_within_engagement_range(self, model, target_unit, *, game_map=None) -> bool:
        if model is None or target_unit is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        source = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        target = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        if game_map is not None and hasattr(game_map, "is_within_engagement_range"):
            return bool(game_map.is_within_engagement_range(source, target))
        if hasattr(unit, "_model_within_engagement_range_of_unit"):
            return bool(unit._model_within_engagement_range_of_unit(model, target))
        return False

    def _target_is_closest_eligible(self, model, weapon_profile, target_unit, *, game_map=None) -> bool:
        if model is None or weapon_profile is None or target_unit is None or game_map is None:
            return False
        try:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is not None and getattr(parent, "is_melee", lambda: False)():
                return False
        except Exception:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None or not hasattr(unit, "is_target_closest_eligible"):
            return False
        target = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        return bool(unit.is_target_closest_eligible(model, weapon_profile, target, game_map))

    def methodical_annihilation_applies(self, model, weapon_profile, target_unit, *, game_map=None) -> bool:
        if not self.is_hearthband():
            return False
        if model is None or weapon_profile is None or target_unit is None:
            return False
        if not self._model_in_army(model):
            return False
        if not self._model_is_votann(model):
            return False
        if self._target_within_engagement_range(model, target_unit, game_map=game_map):
            return True
        return self._target_is_closest_eligible(model, weapon_profile, target_unit, game_map=game_map)

    def methodical_annihilation_reroll_wound_ones(self, model, weapon_profile, target_unit, *, game_map=None) -> bool:
        return bool(self.methodical_annihilation_applies(model, weapon_profile, target_unit, game_map=game_map))

    def methodical_annihilation_ap_bonus(self, model, weapon_profile, target_unit, *, game_map=None) -> int:
        if not self.methodical_annihilation_applies(model, weapon_profile, target_unit, game_map=game_map):
            return 0
        unit = getattr(model, "parent_unit", None)
        if not self._unit_is_methodical_ap_unit(unit):
            return 0
        return 1

