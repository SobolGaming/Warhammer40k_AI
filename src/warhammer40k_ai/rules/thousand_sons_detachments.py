from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .detachment_manager import DetachmentManagerBase
from ..utility.aura_utils import linked_fire_origin_is_visible, unit_within_range_of_unit


@dataclass(frozen=True)
class GrandCovenAbility:
    key: str
    name: str
    summary: str


IMBUED_MANIFESTATION = GrandCovenAbility(
    key="IMBUED_MANIFESTATION",
    name="Imbued Manifestation",
    summary='Add 6" to the Range characteristic of ranged Psychic weapons.',
)
PSYCHIC_MAELSTROM = GrandCovenAbility(
    key="PSYCHIC_MAELSTROM",
    name="Psychic Maelstrom",
    summary="Each time a Psychic weapon attacks, add 1 to the Wound roll.",
)
WRATH_OF_THE_IMMATERIUM = GrandCovenAbility(
    key="WRATH_OF_THE_IMMATERIUM",
    name="Wrath of the Immaterium",
    summary="Psychic weapons gain [Devastating Wounds].",
)

GRAND_COVEN_ABILITIES: tuple[GrandCovenAbility, ...] = (
    IMBUED_MANIFESTATION,
    PSYCHIC_MAELSTROM,
    WRATH_OF_THE_IMMATERIUM,
)
GRAND_COVEN_BY_KEY = {a.key: a for a in GRAND_COVEN_ABILITIES}


class ThousandSonsDetachmentManager(DetachmentManagerBase):
    faction_id = "TS"

    def __init__(self, army=None):
        super().__init__(army)
        self.grand_coven_active_key: Optional[str] = None
        self.grand_coven_active_round: Optional[int] = None
        self.grand_coven_used_keys: list[str] = []
        self.hexwarp_flow_phase_key: Optional[str] = None
        self.hexwarp_flow_zones: set[str] = {"own"}
        self.warpfire_selection_state_by_key: dict[str, dict[str, object]] = {}

    def is_grand_coven(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Grand Coven")

    def _army_has_grand_coven(self) -> bool:
        return self.is_grand_coven()

    def _is_active_round(self, game=None) -> bool:
        if self.grand_coven_active_round is None:
            return False
        if game is None:
            return True
        try:
            return int(getattr(game, "turn", 0) or 0) == int(self.grand_coven_active_round)
        except Exception:
            return False

    def _model_is_thousand_sons(self, model) -> bool:
        if model is None:
            return False
        try:
            fn = getattr(model, "has_any_keyword", None)
            if callable(fn) and fn("THOUSAND SONS"):
                return True
        except Exception:
            pass
        try:
            unit = getattr(model, "parent_unit", None)
        except Exception:
            unit = None
        return self._unit_has_keyword_or_faction(unit, "THOUSAND SONS", faction_id=self.faction_id)

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        try:
            unit = getattr(model, "parent_unit", None)
        except Exception:
            unit = None
        if unit is None:
            return False
        try:
            return unit.get_parent_army() is self.army
        except Exception:
            return False

    def get_available_grand_coven_abilities(self) -> list[GrandCovenAbility]:
        if not self._army_has_grand_coven():
            return []
        used = {str(k or "").strip().upper() for k in (self.grand_coven_used_keys or []) if str(k or "").strip()}
        return [a for a in GRAND_COVEN_ABILITIES if a.key not in used]

    def can_select_grand_coven(self, *, game=None) -> bool:
        if not self._army_has_grand_coven():
            return False
        if self.grand_coven_active_round is not None and self._is_active_round(game=game) and self.grand_coven_active_key:
            return False
        return bool(self.get_available_grand_coven_abilities())

    def select_grand_coven(self, ability, *, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_grand_coven():
            return False
        key = getattr(ability, "key", ability)
        key = str(key or "").strip().upper()
        if key not in GRAND_COVEN_BY_KEY:
            return False
        used = {str(k or "").strip().upper() for k in (self.grand_coven_used_keys or []) if str(k or "").strip()}
        if key in used:
            return False
        self.grand_coven_active_key = key
        if battle_round is not None:
            try:
                self.grand_coven_active_round = int(battle_round)
            except Exception:
                pass
        self.grand_coven_used_keys.append(key)
        return True

    def get_active_grand_coven(self, *, game=None) -> Optional[GrandCovenAbility]:
        if not self._army_has_grand_coven():
            return None
        if not self.grand_coven_active_key:
            return None
        if not self._is_active_round(game=game):
            return None
        return GRAND_COVEN_BY_KEY.get(self.grand_coven_active_key)

    def _grand_coven_applies(self, model, *, game=None) -> bool:
        if not self._army_has_grand_coven():
            return False
        if not self._is_active_round(game=game):
            return False
        if not self._model_is_thousand_sons(model):
            return False
        if not self._model_in_army(model):
            return False
        return True

    def grand_coven_psychic_range_bonus(self, model, weapon_profile=None, *, game=None) -> int:
        active = self.get_active_grand_coven(game=game)
        if active is None or active.key != IMBUED_MANIFESTATION.key:
            return 0
        if not self._grand_coven_applies(model, game=game):
            return 0
        if weapon_profile is None:
            return 0
        try:
            if not bool(getattr(weapon_profile, "is_psychic", lambda: False)()):
                return 0
        except Exception:
            return 0
        try:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_ranged = bool(parent is not None and getattr(parent, "is_ranged", lambda: False)())
        except Exception:
            is_ranged = False
        if not is_ranged:
            return 0
        return 6

    def grand_coven_psychic_wound_bonus(self, model, weapon_profile=None, *, game=None) -> int:
        active = self.get_active_grand_coven(game=game)
        if active is None or active.key != PSYCHIC_MAELSTROM.key:
            return 0
        if not self._grand_coven_applies(model, game=game):
            return 0
        if weapon_profile is None:
            return 0
        try:
            if not bool(getattr(weapon_profile, "is_psychic", lambda: False)()):
                return 0
        except Exception:
            return 0
        return 1

    def grand_coven_devastating_wounds(self, model, weapon_profile=None, *, game=None) -> bool:
        active = self.get_active_grand_coven(game=game)
        if active is None or active.key != WRATH_OF_THE_IMMATERIUM.key:
            return False
        if not self._grand_coven_applies(model, game=game):
            return False
        if weapon_profile is None:
            return False
        try:
            return bool(getattr(weapon_profile, "is_psychic", lambda: False)())
        except Exception:
            return False

    def is_rubricae_phalanx(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Rubricae Phalanx")

    def is_changehost_of_deceit(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Changehost of Deceit")

    def is_hexwarp_thrallband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hexwarp Thrallband")

    def is_warpforged_cabal(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Warpforged Cabal")

    @staticmethod
    def _phase_key_for_game(game) -> str:
        if game is None:
            return ""
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            turn = 0
        phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        get_current_player = getattr(game, "get_current_player", None)
        current_player = get_current_player() if callable(get_current_player) else None
        owner_id = str(getattr(current_player, "id", "") or "")
        return f"{turn}:{phase}:{owner_id}"

    def _resolve_game(self, game=None):
        if game is not None:
            return game
        player = getattr(self.army, "player", None) if self.army is not None else None
        return getattr(player, "game", None) if player is not None else None

    def _compute_hexwarp_flow_zones(self, game) -> set[str]:
        zones: set[str] = {"own"}
        if game is None:
            return zones
        player = getattr(self.army, "player", None) if self.army is not None else None
        if player is None:
            return zones
        game_players = list(getattr(game, "players", None) or [])
        opponent = next((p for p in game_players if p is not player), None)
        game_map = getattr(game, "map", None)
        objectives = list(getattr(game_map, "objectives", None) or [])

        nml_total = 0
        nml_controlled = 0
        enemy_total = 0
        enemy_controlled = 0

        for objective in objectives:
            location = getattr(objective, "location", None)
            if location is None or bool(getattr(location, "removed", False)):
                continue
            update_control = getattr(location, "update_control", None)
            if callable(update_control):
                update_control(game)
            x = float(getattr(location, "x", 0.0) or 0.0)
            y = float(getattr(location, "y", 0.0) or 0.0)
            in_own = bool(game.is_position_in_deployment_zone(x, y, player.id))
            in_enemy = bool(game.is_position_in_deployment_zone(x, y, opponent.id)) if opponent is not None else False
            controller = getattr(location, "controlling_player", None)
            if in_enemy:
                enemy_total += 1
                if controller is player:
                    enemy_controlled += 1
            elif not in_own:
                nml_total += 1
                if controller is player:
                    nml_controlled += 1

        if nml_total > 0 and int(nml_controlled) * 2 >= int(nml_total):
            zones.add("nml")
        if enemy_total > 0 and int(enemy_controlled) * 2 >= int(enemy_total):
            zones.add("enemy")
        return zones

    def on_phase_start(self, *, game=None) -> None:
        if not self.is_hexwarp_thrallband():
            return
        game_obj = self._resolve_game(game=game)
        if game_obj is None:
            return
        self.hexwarp_flow_phase_key = self._phase_key_for_game(game_obj)
        self.hexwarp_flow_zones = self._compute_hexwarp_flow_zones(game_obj)

    def _active_hexwarp_flow_zones(self, game=None) -> set[str]:
        if not self.is_hexwarp_thrallband():
            return {"own"}
        game_obj = self._resolve_game(game=game)
        if game_obj is None:
            return {"own"}
        phase_key = self._phase_key_for_game(game_obj)
        if str(self.hexwarp_flow_phase_key or "") != str(phase_key or ""):
            # Fallback for tests/minimal simulations that do not emit phase_start events.
            self.hexwarp_flow_phase_key = phase_key
            self.hexwarp_flow_zones = self._compute_hexwarp_flow_zones(game_obj)
        zones = {"own"}
        zones.update(set(self.hexwarp_flow_zones or {"own"}))
        return zones

    def _model_wholly_within_hexwarp_flow(self, model, *, game=None) -> bool:
        if model is None:
            return False
        if not bool(getattr(model, "is_alive", True)):
            return False
        game_obj = self._resolve_game(game=game)
        if game_obj is None:
            return False
        player = getattr(self.army, "player", None) if self.army is not None else None
        if player is None:
            return False
        game_players = list(getattr(game_obj, "players", None) or [])
        opponent = next((p for p in game_players if p is not player), None)
        base = getattr(model, "model_base", None)
        get_location = getattr(model, "get_location", None)
        if base is None or not callable(get_location):
            return False
        location = get_location()
        if location is None or len(location) < 2:
            return False
        x = float(location[0] or 0.0)
        y = float(location[1] or 0.0)
        in_own = bool(game_obj.is_position_wholly_in_deployment_zone(x, y, base, player.id))
        in_enemy = bool(game_obj.is_position_wholly_in_deployment_zone(x, y, base, opponent.id)) if opponent is not None else False
        if in_own:
            zone = "own"
        elif in_enemy:
            zone = "enemy"
        else:
            zone = "nml"
        return zone in self._active_hexwarp_flow_zones(game=game_obj)

    def hexwarp_flow_of_magic_psychic_wound_modifiers(self, model, weapon_profile=None, *, game=None) -> tuple[int, bool, str]:
        if not self.is_hexwarp_thrallband():
            return 0, False, ""
        if model is None or weapon_profile is None:
            return 0, False, ""
        if not self._model_in_army(model):
            return 0, False, ""
        if not self._model_is_thousand_sons(model):
            return 0, False, ""
        is_psychic = getattr(weapon_profile, "is_psychic", None)
        if not callable(is_psychic) or not bool(is_psychic()):
            return 0, False, ""
        game_obj = self._resolve_game(game=game)
        if self._model_wholly_within_hexwarp_flow(model, game=game_obj):
            return 1, False, "Flow of Magic"
        return 0, True, "Flow of Magic"

    @staticmethod
    def _normalize_unit_name(name: str) -> str:
        text = str(name or "").strip().lower()
        return " ".join(text.split())

    def _iter_army_units(self) -> list:
        return list(getattr(self.army, "units", []) or [])

    def _attached_unit_root(self, unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
            if root is not None:
                return root
        return unit

    def _iter_unique_army_roots(self) -> list:
        roots: list = []
        seen: set[str] = set()
        for unit in self._iter_army_units():
            root = self._attached_unit_root(unit)
            if root is None:
                continue
            uid = str(getattr(root, "_id", "") or "")
            if not uid:
                uid = str(id(root))
            if uid in seen:
                continue
            seen.add(uid)
            roots.append(root)
        return roots

    @staticmethod
    def _unit_points(unit) -> int:
        get_cost = getattr(unit, "get_unit_cost", None)
        if callable(get_cost):
            try:
                return int(get_cost() or 0)
            except (TypeError, ValueError):
                return 0
            except AttributeError:
                return 0
        raw = getattr(unit, "points", 0)
        try:
            return int(raw or 0)
        except (TypeError, ValueError):
            return 0

    def _unit_is_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        is_alive_fn = getattr(unit, "is_alive", None)
        if callable(is_alive_fn) and not bool(is_alive_fn()):
            return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        in_reserves_fn = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves_fn) and bool(in_reserves_fn()):
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        if getattr(unit, "embarked_in", None) is not None:
            return False
        return True

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if callable(get_parent_army):
            return get_parent_army() is self.army
        return False

    def _attached_unit_has_keyword(self, unit, keyword: str) -> bool:
        root = self._attached_unit_root(unit)
        if root is None:
            return False
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        for member in members:
            if self._unit_has_keyword(member, keyword):
                return True
        return False

    def _unit_is_thousand_sons(self, unit) -> bool:
        return self._attached_unit_has_keyword(unit, "THOUSAND SONS")

    def _unit_is_scintillating_legions(self, unit) -> bool:
        return self._attached_unit_has_keyword(unit, "SCINTILLATING LEGIONS")

    def _unit_is_psyker(self, unit) -> bool:
        return self._attached_unit_has_keyword(unit, "PSYKER")

    def _unit_is_thousand_sons_psyker(self, unit) -> bool:
        return bool(self._unit_is_thousand_sons(unit) and self._unit_is_psyker(unit))

    def _unit_is_scintillating_legions_psyker(self, unit) -> bool:
        return bool(self._unit_is_scintillating_legions(unit) and self._unit_is_psyker(unit))

    def _unit_is_thousand_sons_vehicle(self, unit) -> bool:
        return bool(self._unit_is_thousand_sons(unit) and self._attached_unit_has_keyword(unit, "VEHICLE"))

    @staticmethod
    def _changehost_scintillating_points_cap(points_limit: int) -> tuple[int, str]:
        if points_limit <= 1000:
            return 500, "Incursion"
        if points_limit <= 2000:
            return 1000, "Strike Force"
        return 1500, "Onslaught"

    def _changehost_units_within_visible_range(self, *, source_unit, target_unit, radius: float, game_map=None) -> bool:
        if source_unit is None or target_unit is None:
            return False
        if not self._unit_is_on_battlefield(source_unit):
            return False
        if not self._unit_is_on_battlefield(target_unit):
            return False
        if not unit_within_range_of_unit(source_unit, target_unit, float(radius), use_attached_aggregate=True):
            return False
        if game_map is None:
            return True
        return bool(linked_fire_origin_is_visible(source_unit, target_unit, game_map=game_map))

    def changehost_daemonic_illusions_invulnerable_save(
        self,
        target_model,
        *,
        attack_type: str,
        game_map=None,
    ) -> tuple[int, str]:
        if not self.is_changehost_of_deceit():
            return 0, ""
        if str(attack_type or "").strip().lower() != "ranged":
            return 0, ""
        target_unit = self._attached_unit_root(getattr(target_model, "parent_unit", None))
        if target_unit is None:
            return 0, ""
        if not self._unit_in_army(target_unit):
            return 0, ""
        if not self._unit_is_thousand_sons_psyker(target_unit):
            return 0, ""
        for source in self._iter_unique_army_roots():
            if not self._unit_is_scintillating_legions(source):
                continue
            if not self._changehost_units_within_visible_range(
                source_unit=source,
                target_unit=target_unit,
                radius=6.0,
                game_map=game_map,
            ):
                continue
            return 4, "Daemonic Illusions (Aura)"
        return 0, ""

    def changehost_mortal_sorcery_grants_cabal(self, unit, *, game_map=None) -> bool:
        if not self.is_changehost_of_deceit():
            return False
        target_unit = self._attached_unit_root(unit)
        if target_unit is None:
            return False
        if not self._unit_in_army(target_unit):
            return False
        if not self._unit_is_scintillating_legions_psyker(target_unit):
            return False
        for source in self._iter_unique_army_roots():
            if not self._unit_is_thousand_sons(source):
                continue
            if not self._changehost_units_within_visible_range(
                source_unit=source,
                target_unit=target_unit,
                radius=6.0,
                game_map=game_map,
            ):
                continue
            return True
        return False

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        if not self.is_changehost_of_deceit():
            return errors
        army = self.army
        if army is None:
            return errors
        cap, size_label = self._changehost_scintillating_points_cap(
            int(getattr(army, "points_limit", 0) or 0)
        )
        scint_points = 0
        for unit in self._iter_unique_army_roots():
            if not self._unit_is_scintillating_legions(unit):
                continue
            scint_points += self._unit_points(unit)
        if int(scint_points) > int(cap):
            errors.append(
                "Changehost of Deceit: combined SCINTILLATING LEGIONS points "
                f"({int(scint_points)}) exceed the {size_label} cap of {int(cap)}."
            )

        warlord = getattr(army, "warlord", None)
        if warlord is None:
            for unit in self._iter_unique_army_roots():
                if bool(getattr(unit, "is_warlord", False)):
                    warlord = unit
                    break
        warlord_root = self._attached_unit_root(warlord)
        if warlord_root is not None and self._unit_is_scintillating_legions(warlord_root):
            errors.append(
                "Changehost of Deceit: no SCINTILLATING LEGIONS model from your army can be your WARLORD."
            )
        return errors

    def _model_is_rubricae(self, model) -> bool:
        if model is None:
            return False
        try:
            fn = getattr(model, "has_any_keyword", None)
            if callable(fn) and fn("RUBRICAE"):
                return True
        except Exception:
            pass
        try:
            unit = getattr(model, "parent_unit", None)
        except Exception:
            unit = None
        return self._unit_has_keyword(unit, "RUBRICAE")

    def rubricae_phalanx_armor_save_bonus(
        self,
        model,
        *,
        damage_characteristic: Optional[int] = None,
    ) -> int:
        """
        Detachment ability: All is Dust (Rubricae Phalanx).

        Each time an attack with an unmodified Damage characteristic of 1 is allocated to a
        Rubricae model from your army, add 1 to any armour saving throw made against that attack.
        """
        if not self.is_rubricae_phalanx():
            return 0
        if damage_characteristic is None:
            return 0
        try:
            if int(damage_characteristic) != 1:
                return 0
        except Exception:
            return 0
        if not self._model_is_rubricae(model):
            return 0
        if not self._model_in_army(model):
            return 0
        return 1
