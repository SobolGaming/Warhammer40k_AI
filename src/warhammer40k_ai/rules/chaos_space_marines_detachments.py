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
    DETACHMENT_DECEPTORS = "Deceptors"
    DETACHMENT_DREAD_TALONS = "Dread Talons"
    DETACHMENT_FELLHAMMER_SIEGE_HOST = "Fellhammer Siege-host"
    DETACHMENT_HURONS_MARAUDERS = "Huron's Marauders"
    DETACHMENT_RENEGADE_RAIDERS = "Renegade Raiders"
    _MASTERS_OF_MISDIRECTION_SELECTION_ABILITY = "deceptors_masters_of_misdirection_selection"
    _MASTERS_OF_MISDIRECTION_SOURCE = "Masters of Misdirection"
    _TYRANNICAL_MOTIVATION_ABILITY = "tyrannical_motivation_choice"
    _TYRANNICAL_MOTIVATION_SOURCE = "Tyrannical Motivation"
    _TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE = "HURONS_ELITE"
    _TYRANNICAL_MOTIVATION_CHOICE_MOBILE_MARAUDERS = "MOBILE_MARAUDERS"
    _DESPERATE_DEVOTION_ALLOWED_ACTIONS = {"move", "advance", "charge"}
    _EXPERIMENTAL_AUGMENTATION_REROLL_MODES = {"keep", "reroll_first", "reroll_second", "reroll_both"}

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

    def is_renegade_raiders(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_RENEGADE_RAIDERS)

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

    def terror_descends_source_units(self) -> list:
        if not self.is_dread_talons() or self.army is None:
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
        if not self.is_dread_talons():
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
        updated["battle_shock_suppress_other_tests_source"] = "Terror Descends"
        if bool(allow_current_test):
            updated["battle_shock_allow_suppressed_test"] = True
        else:
            updated.pop("battle_shock_allow_suppressed_test", None)
        root.special_rules = updated

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

    @classmethod
    def _tyrannical_motivation_choice_label(cls, choice_key: str) -> str:
        key = str(choice_key or "").strip().upper()
        if key == cls._TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE:
            return "Huron's Elite"
        if key == cls._TYRANNICAL_MOTIVATION_CHOICE_MOBILE_MARAUDERS:
            return "Mobile Marauders"
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

        choice_key = str(self.tyrannical_motivation_choice_key or "").strip().upper()
        if choice_key not in {
            self._TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE,
            self._TYRANNICAL_MOTIVATION_CHOICE_MOBILE_MARAUDERS,
        }:
            return False, False

        self.refresh_tyrannical_motivation_phase_state(game=game)
        unit_id = self._tyrannical_motivation_unit_id(root)
        if not unit_id:
            return False, False
        has_hit_bonus = bool(choice_key == self._TYRANNICAL_MOTIVATION_CHOICE_HURONS_ELITE)
        has_mobile_marauders = bool(choice_key == self._TYRANNICAL_MOTIVATION_CHOICE_MOBILE_MARAUDERS)
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

    def get_active_experimental_augmentation_keys_for_model(self, model) -> set[str]:
        if not self.is_creations_of_bile():
            return set()
        if not self.experimental_augmentations_selected:
            return set()
        if not self._model_is_creations_eligible(model):
            return set()
        return set(self.experimental_augmentations_active_keys)

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
    def _is_legionaries_unit(cls, unit) -> bool:
        return cls._normalize_name(str(getattr(unit, "name", "") or "")) == "legionaries"

    @classmethod
    def _is_cultist_mob_unit(cls, unit) -> bool:
        return cls._normalize_name(str(getattr(unit, "name", "") or "")) == "cultist mob"

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

    def validate_detachment_rules(self) -> list[str]:
        if self.is_chaos_cult():
            self.apply_chaos_cult_traitor_guardsmen_battleline_keywords()
        return []

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
