from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Optional

from ..utility.ability_support import ABILITY_POWER_FROM_PAIN, army_has_ability_id
from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id
import logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PainTriggerSpec:
    trigger: str
    phase: str
    requires_active_turn: bool = False


@dataclass(frozen=True)
class PainAbilitySpec:
    key: str
    name: str
    triggers: tuple[PainTriggerSpec, ...]


TRIGGER_SHOOTING = "shooting"
TRIGGER_FIGHT = "fight"
TRIGGER_ADVANCE = "advance"
TRIGGER_CHARGE = "charge"
TRIGGER_COMMAND = "command"
TRIGGER_SHOOTING_START = "shooting_start"
TRIGGER_FIGHT_START = "fight_start"
TRIGGER_CHARGE_START = "charge_start"
TRIGGER_MOVEMENT = "movement"
TRIGGER_OPP_FIGHT_END = "opp_fight_end"


SUPPORTED_PAIN_ABILITIES: dict[str, PainAbilitySpec] = {
    "acrobatic gladiators": PainAbilitySpec(
        key="ACROBATIC_GLADIATORS",
        name="Acrobatic Gladiators",
        triggers=(PainTriggerSpec(TRIGGER_CHARGE_START, "CHARGE_PHASE", requires_active_turn=True),),
    ),
    "archon of the poisoned tongue": PainAbilitySpec(
        key="ARCHON_POISONED_TONGUE",
        name="Archon of the Poisoned Tongue",
        triggers=(
            PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),
            PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),
        ),
    ),
    "assassins poisons": PainAbilitySpec(
        key="ASSASSINS_POISONS",
        name="Assassins' Poisons",
        triggers=(
            PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),
            PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),
        ),
    ),
    "battlefield butchery": PainAbilitySpec(
        key="BATTLEFIELD_BUTCHERY",
        name="Battlefield Butchery",
        triggers=(PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),),
    ),
    "hatred eternal": PainAbilitySpec(
        key="HATRED_ETERNAL",
        name="Hatred Eternal",
        triggers=(
            PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),
            PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),
        ),
    ),
    "lithe agility": PainAbilitySpec(
        key="LITHE_AGILITY",
        name="Lithe Agility",
        triggers=(
            PainTriggerSpec(TRIGGER_ADVANCE, "MOVEMENT_PHASE", requires_active_turn=True),
            PainTriggerSpec(TRIGGER_CHARGE, "CHARGE_PHASE", requires_active_turn=True),
        ),
    ),
    "brides of death": PainAbilitySpec(
        key="BRIDES_OF_DEATH",
        name="Brides of Death",
        triggers=(PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),),
    ),
    "deadly retinue": PainAbilitySpec(
        key="DEADLY_RETINUE",
        name="Deadly Retinue",
        triggers=(
            PainTriggerSpec(TRIGGER_SHOOTING_START, "SHOOTING_PHASE", requires_active_turn=True),
            PainTriggerSpec(TRIGGER_FIGHT_START, "FIGHT_PHASE", requires_active_turn=False),
        ),
    ),
    "decapitating strikes": PainAbilitySpec(
        key="DECAPITATING_STRIKES",
        name="Decapitating Strikes",
        triggers=(PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),),
    ),
    "electromagentic cascade": PainAbilitySpec(
        key="ELECTROMAGENTIC_CASCADE",
        name="Electromagentic Cascade",
        triggers=(PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),),
    ),
    "engine of destruction": PainAbilitySpec(
        key="ENGINE_OF_DESTRUCTION",
        name="Engine of Destruction",
        triggers=(PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),),
    ),
    "experimental enhancements": PainAbilitySpec(
        key="EXPERIMENTAL_ENHANCEMENTS",
        name="Experimental Enhancements",
        triggers=(PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),),
    ),
    "fade away": PainAbilitySpec(
        key="FADE_AWAY",
        name="Fade Away",
        triggers=(PainTriggerSpec(TRIGGER_OPP_FIGHT_END, "FIGHT_PHASE", requires_active_turn=False),),
    ),
    "sculptor of torments": PainAbilitySpec(
        key="SCULPTOR_OF_TORMENTS",
        name="Sculptor of Torments",
        triggers=(PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),),
    ),
    "master of blades": PainAbilitySpec(
        key="MASTER_OF_BLADES",
        name="Master of Blades",
        triggers=(PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),),
    ),
    "matchless swiftness": PainAbilitySpec(
        key="MATCHLESS_SWIFTNESS",
        name="Matchless Swiftness",
        triggers=(PainTriggerSpec(TRIGGER_ADVANCE, "MOVEMENT_PHASE", requires_active_turn=True),),
    ),
    "mindless killing machines": PainAbilitySpec(
        key="MINDLESS_KILLING_MACHINES",
        name="Mindless Killing Machines",
        triggers=(PainTriggerSpec(TRIGGER_FIGHT_START, "FIGHT_PHASE", requires_active_turn=False),),
    ),
    "macro steroids": PainAbilitySpec(
        key="MACRO_STEROIDS",
        name="Macro-steroids",
        triggers=(PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),),
    ),
    "goaded savagery": PainAbilitySpec(
        key="GOADED_SAVAGERY",
        name="Goaded Savagery",
        triggers=(PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),),
    ),
    "shredding fire": PainAbilitySpec(
        key="SHREDDING_FIRE",
        name="Shredding Fire",
        triggers=(PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),),
    ),
    "sadistic raiders": PainAbilitySpec(
        key="SADISTIC_RAIDERS",
        name="Sadistic Raiders",
        triggers=(
            PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),
            PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),
        ),
    ),
    "splinter racks": PainAbilitySpec(
        key="SPLINTER_RACKS",
        name="Splinter Racks",
        triggers=(PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),),
    ),
    "winged strike": PainAbilitySpec(
        key="WINGED_STRIKE",
        name="Winged Strike",
        triggers=(PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),),
    ),
    "nowhere to run": PainAbilitySpec(
        key="NOWHERE_TO_RUN",
        name="Nowhere to Run",
        triggers=(PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),),
    ),
    "nowhere to hide": PainAbilitySpec(
        key="NOWHERE_TO_HIDE",
        name="Nowhere to Hide",
        triggers=(PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),),
    ),
    "agonising suppression": PainAbilitySpec(
        key="AGONISING_SUPPRESSION",
        name="Agonising Suppression",
        triggers=(PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),),
    ),
    "pain parasite": PainAbilitySpec(
        key="PAIN_PARASITE",
        name="Pain Parasite",
        triggers=(
            PainTriggerSpec(TRIGGER_SHOOTING, "SHOOTING_PHASE", requires_active_turn=True),
            PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),
        ),
    ),
    "rapid deployment": PainAbilitySpec(
        key="RAPID_DEPLOYMENT",
        name="Rapid Deployment",
        triggers=(PainTriggerSpec(TRIGGER_ADVANCE, "MOVEMENT_PHASE", requires_active_turn=True),),
    ),
    "swooping descent": PainAbilitySpec(
        key="SWOOPING_DESCENT",
        name="Swooping Descent",
        triggers=(PainTriggerSpec(TRIGGER_MOVEMENT, "MOVEMENT_PHASE", requires_active_turn=True),),
    ),
    "fleshcraft": PainAbilitySpec(
        key="FLESHCRAFT",
        name="Fleshcraft",
        triggers=(PainTriggerSpec(TRIGGER_COMMAND, "COMMAND_PHASE", requires_active_turn=True),),
    ),
}


def _norm_ability_name(name: str) -> str:
    raw = str(name or "").strip().lower()
    raw = re.sub(r"\(pain\)", "", raw).strip()
    raw = re.sub(r"[^a-z0-9 ]+", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


class PowerFromPainManager:
    """
    Drukhari army rule: Power from Pain.

    Tracks Pain tokens and limited support for select Pain abilities.
    """

    def __init__(self, army=None):
        self.army = army
        self.tokens: int = 0
        self._pending_empowerments: dict[str, dict] = {}

    def _army_has_power_from_pain(self) -> bool:
        if self.army is None:
            return False
        return army_has_ability_id(self.army, ABILITY_POWER_FROM_PAIN)

    def _unit_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if not bool(getattr(unit, "deployed", False)):
                return False
            if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
                return False
        except Exception:
            return False
        try:
            if getattr(unit, "embarked_in", None) is not None:
                return False
        except Exception:
            pass
        try:
            if bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            pass
        return True

    def _unit_is_alive(self, unit) -> bool:
        try:
            return bool(getattr(unit, "is_alive", lambda: True)())
        except Exception:
            try:
                return any(bool(getattr(m, "is_alive", True)) for m in (getattr(unit, "models", []) or []))
            except Exception:
                return False

    def _unit_in_reserves(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return bool(getattr(unit, "is_in_reserves", lambda: False)())
        except Exception:
            try:
                return str(getattr(unit, "reserve_status", "deployed")) in ("reserves", "strategic_reserves")
            except Exception:
                return False

    def _unit_has_model_named(self, unit, needle: str) -> bool:
        if unit is None:
            return False
        want = str(needle or "").strip().lower()
        if not want:
            return False
        try:
            models = list(getattr(unit, "models", []) or [])
        except Exception:
            models = []
        for model in models:
            try:
                name = str(getattr(model, "name", "") or "").lower()
            except Exception:
                name = ""
            if want and want in name:
                return True
        return False

    def _iter_unit_members(self, unit):
        if unit is None:
            return []
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return []
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        return list(members or [root])

    def _unit_has_dark_vitality(self, unit) -> bool:
        for member in self._iter_unit_members(unit):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_dark_vitality", False)):
                continue
            bearer_fn = getattr(member, "_get_enhancement_bearer_model", None)
            bearer = bearer_fn() if callable(bearer_fn) else None
            if bearer is None:
                if self._unit_is_alive(member):
                    return True
                continue
            alive_attr = getattr(bearer, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if is_alive:
                return True
        return False

    def _unit_has_ability_named(self, unit, ability_name: str) -> bool:
        want = _norm_ability_name(ability_name)
        if unit is None or not want:
            return False
        for member in self._iter_unit_members(unit):
            try:
                possible = list(getattr(member, "possible_abilities", []) or [])
            except Exception:
                possible = []
            for ab in possible:
                try:
                    name = ab if isinstance(ab, str) else getattr(ab, "name", "")
                except Exception:
                    name = ""
                norm = _norm_ability_name(name)
                if norm == want:
                    return True
            try:
                models = list(getattr(member, "models", []) or [])
            except Exception:
                models = []
            for model in models:
                try:
                    abilities = list(getattr(model, "abilities", []) or [])
                except Exception:
                    abilities = []
                for ab in abilities:
                    try:
                        name = ab if isinstance(ab, str) else getattr(ab, "name", "")
                    except Exception:
                        name = ""
                    norm = _norm_ability_name(name)
                    if norm == want:
                        return True
        return False

    def _unit_has_master_regenesist(self, unit) -> bool:
        if unit is None:
            return False
        for member in self._iter_unit_members(unit):
            sr = getattr(member, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("enhancement_master_regenesist", False)):
                return True
            enh = getattr(member, "enhancement", None)
            if enh is None:
                continue
            enh_id = str(getattr(enh, "id", "") or "").strip()
            enh_name = str(getattr(enh, "name", "") or "").strip().lower()
            if enh_id == "000010584002" or enh_name == "master regenesist":
                return True
        return False

    def _sadistic_fulcrum_transport_candidates_for_unit(self, unit, *, game=None) -> list:
        del game
        if unit is None:
            return []
        army = self.army
        mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
        candidate_fn = (
            getattr(mgr, "skysplinter_sadistic_fulcrum_transport_candidates", None)
            if mgr is not None
            else None
        )
        if not callable(candidate_fn):
            return []
        raw_candidates = candidate_fn(unit)
        if raw_candidates is None:
            return []
        candidates = list(raw_candidates)
        return [entry for entry in candidates if entry is not None]

    def _unit_has_sadistic_fulcrum(self, unit) -> bool:
        if unit is None:
            return False
        for member in self._iter_unit_members(unit):
            sr = getattr(member, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("enhancement_sadistic_fulcrum", False)):
                return True
        return False

    def _model_has_wargear_named(self, model, wargear_name: str) -> bool:
        want = str(wargear_name or "").strip().lower()
        want = re.sub(r"[^a-z0-9]+", " ", want)
        want = re.sub(r"\s+", " ", want).strip()
        if model is None or not want:
            return False
        try:
            wargear = list(getattr(model, "wargear", []) or [])
        except Exception:
            wargear = []
        for wg in wargear:
            try:
                name = str(getattr(wg, "name", "") or "").strip().lower()
            except Exception:
                name = ""
            name = re.sub(r"[^a-z0-9]+", " ", name)
            name = re.sub(r"\s+", " ", name).strip()
            if name == want:
                return True
        try:
            optional_wargear = list(getattr(model, "optional_wargear", []) or [])
        except Exception:
            optional_wargear = []
        for wg in optional_wargear:
            name = str(wg or "").strip().lower()
            name = re.sub(r"[^a-z0-9]+", " ", name)
            name = re.sub(r"\s+", " ", name).strip()
            if name == want:
                return True
        return False

    def _pain_engine_sources_for_empower(self, empowered_unit, *, game=None) -> list:
        if empowered_unit is None or game is None:
            return []
        game_map = getattr(game, "map", None)
        if game_map is None:
            return []
        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return []
        try:
            empowered_root = empowered_unit.get_attached_unit_root()
        except Exception:
            empowered_root = empowered_unit
        if empowered_root is None:
            return []

        results = []
        seen: set[str] = set()
        for candidate in list(getattr(self.army, "units", []) or []):
            if candidate is None:
                continue
            try:
                source = candidate.get_attached_unit_root()
            except Exception:
                source = candidate
            if source is None:
                continue
            source_id = str(get_entity_id(source) or "")
            if not source_id or source_id in seen:
                continue
            seen.add(source_id)
            if not self._unit_is_alive(source):
                continue
            if not self._unit_on_battlefield(source):
                continue
            if not self._unit_has_ability_named(source, "Pain Engine (Aura)"):
                continue
            try:
                if not unit_within_range_of_unit(source, empowered_root, 9.0, use_attached_aggregate=True):
                    continue
            except Exception:
                continue
            results.append(source)
        return results

    def _pain_engine_roll_bonus(self, pain_engine_unit) -> int:
        if pain_engine_unit is None:
            return 0
        try:
            models = list(getattr(pain_engine_unit, "models", []) or [])
        except Exception:
            models = []
        if not models:
            return 0
        for model in models:
            try:
                alive = bool(getattr(model, "is_alive", True))
            except Exception:
                alive = True
            if not alive:
                continue
            if not self._model_has_wargear_named(model, "spirit vortex"):
                return 1
        return 0

    def _apply_pain_engine_refund_on_empower(self, empowered_unit, *, game=None) -> None:
        if not self._army_has_power_from_pain():
            return
        sources = self._pain_engine_sources_for_empower(empowered_unit, game=game)
        if not sources:
            return
        player = getattr(self.army, "player", None)
        for source in sources:
            bonus = self._pain_engine_roll_bonus(source)
            roll = int(get_roll("D6"))
            total = int(roll + bonus)
            try:
                from ..utility.event_bus import append_dice

                if bonus:
                    append_dice(
                        player,
                        f"Pain Engine roll ({getattr(source, 'name', 'Pain Engine')}): {roll}+{bonus}={total}",
                    )
                else:
                    append_dice(
                        player,
                        f"Pain Engine roll ({getattr(source, 'name', 'Pain Engine')}): {roll}",
                    )
            except Exception:
                pass
            if total >= 5:
                self.gain_tokens(1, reason=f"Pain Engine ({getattr(source, 'name', 'Unit')})")

    def _unit_owner(self, unit):
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        return getattr(army, "player", None) if army is not None else None

    def _phase_name(self, game) -> str:
        try:
            return str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            return ""

    def _pending_empowerment_key(self, unit_id: str, trigger: str, phase_name: str) -> str:
        return f"{unit_id}:{trigger}:{phase_name}"

    def _resolve_unit_by_id(self, unit_id: str, *, game=None):
        if not unit_id:
            return None
        if game is not None:
            registry = getattr(game, "entity_registry", None)
            if registry is not None:
                try:
                    unit = registry.get(str(unit_id), kind="unit")
                except Exception:
                    unit = None
                if unit is not None:
                    return unit
        try:
            for unit in list(getattr(self.army, "units", []) or []):
                try:
                    if str(get_entity_id(unit)) == str(unit_id):
                        return unit
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _pending_choice_request(self, game, pending_key: str, choice_kind: str) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            try:
                if str(getattr(req, "decision_type", "")) != "CHOOSE_POWER_FROM_PAIN_OPTION":
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("pending_key", "")) != str(pending_key):
                    continue
                if str(ctx.get("choice_kind", "")) != str(choice_kind):
                    continue
                return True
            except Exception:
                continue
        return False

    def _queue_choice_request(self, *, game, player, unit_id: str, choice_kind: str, pending_key: str) -> None:
        if game is None:
            return
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_POWER_FROM_PAIN_OPTION
            from ..engine.decisions import DecisionOption, DecisionRequest
        except Exception:
            return

        if choice_kind == "archon_poisoned_tongue":
            title = "Archon of the Poisoned Tongue"
            options = [
                DecisionOption.create("Lethal Hits", payload={"choice_key": "LETHAL", "choice_kind": choice_kind, "unit_id": unit_id}),
                DecisionOption.create("Sustained Hits 1", payload={"choice_key": "SUSTAINED", "choice_kind": choice_kind, "unit_id": unit_id}),
            ]
        elif choice_kind == "experimental_enhancements":
            title = "Experimental Enhancements"
            options = [
                DecisionOption.create("Attacks 3", payload={"choice_key": "ATTACKS_3", "choice_kind": choice_kind, "unit_id": unit_id}),
                DecisionOption.create(
                    "Attacks 4 (Hazardous)",
                    payload={"choice_key": "ATTACKS_4_HAZARDOUS", "choice_kind": choice_kind, "unit_id": unit_id},
                ),
            ]
        elif choice_kind == "master_regenesist":
            title = "Master Regenesist"
            options = [
                DecisionOption.create(
                    "Return D3+3 Models",
                    payload={"choice_key": "ENHANCED", "choice_kind": choice_kind, "unit_id": unit_id},
                ),
                DecisionOption.create(
                    "Return D3+1 Models",
                    payload={"choice_key": "BASE", "choice_kind": choice_kind, "unit_id": unit_id},
                ),
            ]
        elif choice_kind == "sadistic_fulcrum_transport":
            title = "Sadistic Fulcrum"
            source_unit = self._resolve_unit_by_id(unit_id, game=game)
            candidates = self._sadistic_fulcrum_transport_candidates_for_unit(source_unit, game=game)
            if not candidates:
                return
            options = [
                DecisionOption.create(
                    "None",
                    payload={"choice_key": "NONE", "choice_kind": choice_kind, "unit_id": unit_id},
                )
            ]
            for candidate in candidates:
                candidate_id = str(get_entity_id(candidate) or "")
                if not candidate_id:
                    continue
                label = str(getattr(candidate, "name", "") or "Transport").strip() or "Transport"
                options.append(
                    DecisionOption.create(
                        label,
                        payload={"choice_key": candidate_id, "choice_kind": choice_kind, "unit_id": unit_id},
                    )
                )
            if len(options) <= 1:
                return
        else:
            return

        req = DecisionRequest.create(
            DECISION_CHOOSE_POWER_FROM_PAIN_OPTION,
            f"Select {title}.",
            player_id=getattr(player, "id", None),
            options=options,
            context={"unit_id": unit_id, "choice_kind": choice_kind, "pending_key": pending_key},
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)

    def record_empowerment_choice(self, *, pending_key: str, choice_kind: str, choice: str, game=None) -> bool:
        pending = self._pending_empowerments.get(str(pending_key))
        if not isinstance(pending, dict):
            return False
        choices = pending.setdefault("choices", {})
        choices[str(choice_kind)] = str(choice)
        required = list(pending.get("required_choices", []) or [])
        if any(kind for kind in required if kind not in choices):
            return False
        return bool(self._finalize_pending_empowerment(pending_key, game=game))

    def _finalize_pending_empowerment(self, pending_key: str, *, game=None) -> bool:
        pending = self._pending_empowerments.get(str(pending_key))
        if not isinstance(pending, dict):
            return False
        unit_id = str(pending.get("unit_id", "") or "")
        trigger = str(pending.get("trigger", "") or "")
        phase_name = str(pending.get("phase_name", "") or "")
        spec_keys = list(pending.get("spec_keys", []) or [])
        ability_names = list(pending.get("ability_names", []) or [])
        choice_cache = dict(pending.get("choices", {}) or {})
        if not unit_id or not trigger:
            return False
        unit = self._resolve_unit_by_id(unit_id, game=game)
        if unit is None:
            return False
        if not bool(pending.get("tokens_spent", False)):
            if not self.spend_tokens(1, reason=f"Empower ({trigger})"):
                return False
            pending["tokens_spent"] = True
        applied = self._apply_empowerment_effects(
            unit,
            spec_keys=spec_keys,
            ability_names=ability_names,
            choice_cache=choice_cache,
            game=game,
            phase_name=phase_name,
        )
        if applied:
            self._pending_empowerments.pop(str(pending_key), None)
        return bool(applied)

    def _trigger_allows(self, trigger_spec: PainTriggerSpec, *, unit, game) -> bool:
        if trigger_spec is None or game is None or unit is None:
            return False
        phase_name = self._phase_name(game)
        if phase_name and phase_name != trigger_spec.phase:
            return False
        if trigger_spec.requires_active_turn:
            try:
                if getattr(game, "get_current_player", None) is None:
                    return False
                if game.get_current_player() is not self._unit_owner(unit):
                    return False
            except Exception:
                return False
        return True

    def _unit_pain_specs(self, unit) -> list[PainAbilitySpec]:
        if unit is None:
            return []
        specs = []
        try:
            members = unit.get_attached_unit_members()
        except Exception:
            members = [unit]
        for u in list(members or []):
            for ab in list(getattr(u, "possible_abilities", []) or []):
                try:
                    name = ab if isinstance(ab, str) else getattr(ab, "name", "")
                except Exception:
                    name = ""
                key = _norm_ability_name(name)
                if not key:
                    continue
                spec = SUPPORTED_PAIN_ABILITIES.get(key)
                if spec is not None:
                    specs.append(spec)
        # Deduplicate by key while preserving order
        deduped = []
        seen = set()
        for spec in specs:
            if spec.key in seen:
                continue
            seen.add(spec.key)
            deduped.append(spec)
        return deduped

    def _applicable_pain_specs(self, unit, *, trigger: str, game) -> list[PainAbilitySpec]:
        specs = self._unit_pain_specs(unit)
        if not specs:
            return []
        usable = []
        for spec in specs:
            for t in spec.triggers:
                if t.trigger != trigger:
                    continue
                if not self._trigger_allows(t, unit=unit, game=game):
                    continue
                if not self._spec_additional_requirements(spec, unit=unit, game=game):
                    continue
                usable.append(spec)
                break
        return usable

    def _spec_additional_requirements(self, spec: PainAbilitySpec, *, unit, game) -> bool:
        if spec is None or unit is None:
            return False
        key = str(getattr(spec, "key", "") or "").strip().upper()
        if key == "SWOOPING_DESCENT":
            if not self._unit_in_reserves(unit):
                return False
            try:
                if hasattr(unit, "has_deep_strike") and not unit.has_deep_strike():
                    return False
            except Exception:
                return False
        if key == "DEADLY_RETINUE":
            if not (
                self._unit_has_model_named(unit, "lhamaean")
                or self._unit_has_model_named(unit, "medusae")
                or self._unit_has_model_named(unit, "sslyth")
            ):
                return False
        if key == "GOADED_SAVAGERY":
            if not self._unit_has_model_named(unit, "beastmaster"):
                return False
        if key == "FADE_AWAY":
            if game is None or getattr(game, "map", None) is None:
                return False
            try:
                for enemy in list(game.map.get_enemy_units(unit) or []):
                    if not getattr(enemy, "is_alive", lambda: True)():
                        continue
                    if game.map.is_within_engagement_range(unit, enemy):
                        return False
            except Exception:
                return False
        return True

    def _has_pain_adept(self, unit) -> bool:
        return bool(self._unit_has_ability_named(unit, "Pain Adept"))

    def gain_tokens(self, amount: int, *, reason: str = "") -> int:
        if not self._army_has_power_from_pain():
            return 0
        try:
            amount = int(amount or 0)
        except Exception:
            amount = 0
        if amount <= 0:
            return 0
        self.tokens = int(self.tokens or 0) + amount
        try:
            logger.info(f"Power from Pain: +{amount} token(s) ({reason})")
        except Exception:
            pass
        return amount

    def spend_tokens(self, amount: int, *, reason: str = "") -> bool:
        try:
            amount = int(amount or 0)
        except Exception:
            amount = 0
        if amount <= 0:
            return True
        if int(self.tokens or 0) < amount:
            return False
        self.tokens = int(self.tokens or 0) - amount
        try:
            logger.info(f"Power from Pain: -{amount} token(s) ({reason})")
        except Exception:
            pass
        return True

    # ---------------- Token gain hooks ----------------

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if not self._army_has_power_from_pain():
            return
        if player is None or player is not getattr(self.army, "player", None):
            return
        # Start of your Command phase: gain 1 Pain token.
        self.gain_tokens(1, reason="Command phase")
        # Pain Adept: if any models with Pain Adept are on the battlefield, roll 4+ for +1 token.
        pain_adept_present = False
        for u in list(getattr(self.army, "units", []) or []):
            if not self._has_pain_adept(u):
                continue
            if not self._unit_on_battlefield(u):
                continue
            if not self._unit_is_alive(u):
                continue
            pain_adept_present = True
            break
        if not pain_adept_present:
            return
        roll = int(get_roll("D6"))
        try:
            from ..utility.event_bus import append_dice
            append_dice(player, f"Pain Adept roll: {roll}")
        except Exception:
            pass
        if roll >= 4:
            self.gain_tokens(1, reason="Pain Adept (4+)")

    def on_enemy_unit_destroyed(self, unit, *, destroyed_by_unit=None) -> None:
        if not self._army_has_power_from_pain():
            return
        if unit is None:
            return
        try:
            if unit.get_parent_army() is self.army:
                return
        except Exception:
            return
        self.gain_tokens(1, reason="Enemy unit destroyed")
        if destroyed_by_unit is None:
            return
        try:
            source_root = destroyed_by_unit.get_attached_unit_root()
        except Exception:
            source_root = destroyed_by_unit
        if source_root is None:
            return
        try:
            if source_root.get_parent_army() is not self.army:
                return
        except Exception:
            return
        if not self._unit_has_ability_named(source_root, "Torture Device"):
            return
        self.gain_tokens(1, reason="Torture Device")

    def on_enemy_battle_shock_failed(self, unit) -> None:
        if not self._army_has_power_from_pain():
            return
        if unit is None:
            return
        try:
            if unit.get_parent_army() is self.army:
                return
        except Exception:
            return
        self.gain_tokens(1, reason="Enemy Battle-shock failed")

    # ---------------- Empowerment ----------------

    def get_applicable_pain_ability_names(self, unit, *, trigger: str, game) -> list[str]:
        return [spec.name for spec in self._applicable_pain_specs(unit, trigger=trigger, game=game)]

    def _empowered_this_phase(self, unit, phase_name: str) -> bool:
        try:
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict):
                exp = str(sr.get("pain_empowered_expires_phase", "") or "").strip().upper()
                return bool(exp and exp == phase_name)
        except Exception:
            return False
        return False

    def _apply_empowered_markers(self, unit, *, phase_name: str, ability_names: Iterable[str]) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_empowered"] = True
        sr["pain_empowered_expires_phase"] = phase_name
        try:
            existing = list(sr.get("pain_empowered_sources", []) or [])
        except Exception:
            existing = []
        merged = []
        seen = set()
        for name in list(existing) + [str(n) for n in ability_names]:
            n = str(name or "").strip()
            if not n or n in seen:
                continue
            seen.add(n)
            merged.append(n)
        if merged:
            sr["pain_empowered_sources"] = merged
        unit.special_rules = sr

    def _apply_hatred_eternal(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_reroll_hit"] = True
        unit.special_rules = sr

    def _apply_lithe_agility(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_reroll_advance"] = True
        sr["pain_reroll_charge"] = True
        unit.special_rules = sr

    def _apply_brides_of_death(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_melee_strength_bonus"] = int(sr.get("pain_melee_strength_bonus", 0) or 0) + 1
        sr["pain_melee_ap_bonus"] = int(sr.get("pain_melee_ap_bonus", 0) or 0) + 1
        unit.special_rules = sr

    def _apply_sculptor_of_torments(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_melee_wound_bonus"] = int(sr.get("pain_melee_wound_bonus", 0) or 0) + 1
        unit.special_rules = sr

    def _apply_master_of_blades(self, unit) -> None:
        self._apply_sculptor_of_torments(unit)

    def _apply_battlefield_butchery(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_melee_attacks_bonus"] = int(sr.get("pain_melee_attacks_bonus", 0) or 0) + 1
        sr["pain_melee_strength_bonus"] = int(sr.get("pain_melee_strength_bonus", 0) or 0) + 1
        unit.special_rules = sr

    def _apply_acrobatic_gladiators(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_charge_after_advance"] = True
        sr["pain_charge_after_fall_back"] = True
        unit.special_rules = sr

    def _choose_archon_poisoned_tongue(self, unit, *, game=None) -> str:
        return "LETHAL"

    def _apply_archon_poisoned_tongue(self, unit, choice: Optional[str]) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        choice_norm = str(choice or "").strip().upper()
        sr["pain_archon_poisoned_tongue_choice"] = choice_norm or "LETHAL"
        if choice_norm == "SUSTAINED":
            sr["pain_sustained_hits_value"] = max(int(sr.get("pain_sustained_hits_value", 0) or 0), 1)
        else:
            sr["pain_lethal_hits"] = True
        unit.special_rules = sr

    def _apply_assassins_poisons(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_assassins_poisons_active"] = True
        unit.special_rules = sr

    def _apply_deadly_retinue(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if self._unit_has_model_named(unit, "lhamaean"):
            sr["pain_lethal_hits_melee"] = True
        if self._unit_has_model_named(unit, "medusae"):
            sr["pain_ignores_cover_ranged"] = True
        if self._unit_has_model_named(unit, "sslyth"):
            sr["pain_melee_wound_roll_defense_mod"] = -1
        unit.special_rules = sr

    def _apply_decapitating_strikes(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_devastating_vs_infantry"] = True
        unit.special_rules = sr

    def _apply_electromagentic_cascade(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_sustained_hits_ranged_vs_vehicle"] = 2
        sr["pain_sustained_hits_ranged_vs_non_vehicle"] = 1
        unit.special_rules = sr

    def _apply_engine_of_destruction(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        bonuses = dict(sr.get("pain_rapid_fire_weapon_bonus", {}) or {})
        bonuses["pulse disintegrators"] = 8
        sr["pain_rapid_fire_weapon_bonus"] = bonuses
        unit.special_rules = sr

    def _choose_experimental_enhancements(self, unit, *, game=None) -> str:
        return "ATTACKS_3"

    def _apply_experimental_enhancements(self, unit, choice: Optional[str]) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        choice_norm = str(choice or "").strip().upper()
        if choice_norm == "ATTACKS_4_HAZARDOUS":
            sr["pain_melee_attacks_set_non_character"] = 4
            sr["pain_melee_hazardous_non_character"] = True
        else:
            sr["pain_melee_attacks_set_non_character"] = 3
        sr["pain_experimental_enhancements_choice"] = choice_norm or "ATTACKS_3"
        unit.special_rules = sr

    def _apply_goaded_savagery(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_beast_reroll_hit"] = True
        sr["pain_beast_reroll_wound"] = True
        unit.special_rules = sr

    def _apply_macro_steroids(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_melee_strength_set"] = 8
        sr["pain_lethal_hits_melee"] = True
        unit.special_rules = sr

    def _apply_matchless_swiftness(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        tag = "pain:matchless_swiftness"
        effects = list(sr.get("advance_no_roll_effects", []) or [])
        effects = [e for e in effects if not (isinstance(e, dict) and e.get("tag") == tag)]
        effects.append(
            {
                "distance": 8,
                "source": "Matchless Swiftness (Pain)",
                "expires_phase": "MOVEMENT_PHASE",
                "tag": tag,
            }
        )
        sr["advance_no_roll_effects"] = effects
        unit.special_rules = sr

    def _apply_mindless_killing_machines(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_fight_on_death_2plus"] = True
        unit.special_rules = sr

    def _apply_nowhere_to_run(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_shoot_pin"] = True
        unit.special_rules = sr

    def _apply_nowhere_to_hide(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_shoot_no_cover"] = True
        unit.special_rules = sr

    def _apply_agonising_suppression(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_shoot_suppress"] = True
        unit.special_rules = sr

    def _apply_pain_parasite(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_on_kill_heal"] = True
        unit.special_rules = sr

    def _apply_rapid_deployment(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_rapid_deployment_active"] = True
        unit.special_rules = sr

    def _apply_sadistic_raiders(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_reroll_wound_ones"] = True
        sr["pain_reroll_wound_full_if_objective"] = True
        unit.special_rules = sr

    def _apply_shredding_fire(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_ranged_ap_bonus"] = int(sr.get("pain_ranged_ap_bonus", 0) or 0) + 1
        unit.special_rules = sr

    def _apply_splinter_racks(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_splinter_racks_active"] = True
        unit.special_rules = sr

    def _apply_swooping_descent(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_deep_strike_min_distance"] = 6.0
        unit.special_rules = sr

    def _apply_winged_strike(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["pain_reroll_hit_ranged"] = True
        unit.special_rules = sr

    def _apply_fade_away(self, unit, *, game=None) -> bool:
        if unit is None or game is None:
            return False
        game_map = getattr(game, "map", None)
        if game_map is None:
            return False
        try:
            for enemy in list(game_map.get_enemy_units(unit) or []):
                if not getattr(enemy, "is_alive", lambda: True)():
                    continue
                if game_map.is_within_engagement_range(unit, enemy):
                    return False
        except Exception:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return False
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            try:
                if hasattr(member, "set_reserve_status"):
                    member.set_reserve_status("strategic_reserves")
                else:
                    member.reserve_status = "strategic_reserves"
            except Exception:
                pass
            try:
                if hasattr(member, "mark_entered_reserves_midgame"):
                    member.mark_entered_reserves_midgame(game=game)
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
        try:
            logger.info(f"Power from Pain: {root.name} removed into Strategic Reserves (Fade Away)")
        except Exception:
            pass
        return True

    def apply_pain_parasite_heal(self, unit, *, game=None) -> int:
        if unit is None:
            return 0
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return 0

        # Prefer healing a wounded model.
        for model in list(getattr(root, "models", []) or []):
            try:
                if not getattr(model, "is_alive", True):
                    continue
            except Exception:
                continue
            try:
                base = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
                cur = int(getattr(model, "wounds", 0) or 0)
            except Exception:
                continue
            if base <= 0 or cur >= base:
                continue
            healed = min(3, base - cur)
            try:
                model.wounds = cur + healed
            except Exception:
                try:
                    model._wounds = cur + healed
                except Exception:
                    pass
            try:
                if hasattr(model, "_check_damaged_profile"):
                    model._check_damaged_profile()
            except Exception:
                pass
            return int(healed)

        # If all models are at full wounds and the unit is below starting strength, return one model.
        destroyed = list(getattr(root, "models_lost", []) or [])
        if not destroyed:
            return 0
        model = destroyed[0]
        try:
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
            base = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
        except Exception:
            base = 0
        wounds = 3 if base <= 0 else min(3, base)
        try:
            model.wounds = wounds
        except Exception:
            try:
                model._wounds = wounds
            except Exception:
                pass
        try:
            setattr(model, "_on_death_reactions_resolved", False)
            setattr(model, "_fight_on_death_used", False)
            setattr(model, "_shoot_on_death_used", False)
        except Exception:
            pass
        try:
            if hasattr(root, "add_model"):
                root.add_model(model)
            else:
                root.models.append(model)
        except Exception:
            pass
        try:
            if hasattr(root, "update_coherency"):
                root.update_coherency()
        except Exception:
            pass
        return 1

    def _return_destroyed_bodyguard_models(self, unit, *, amount: int, game_map=None) -> int:
        if unit is None:
            return 0
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return 0
        try:
            if bool(getattr(root, "is_leader", False)):
                return 0
        except Exception:
            pass
        destroyed = list(getattr(root, "models_lost", []) or [])
        if not destroyed:
            return 0
        to_return = destroyed[: max(0, int(amount or 0))]
        if not to_return:
            return 0
        try:
            alive_models = [m for m in (getattr(root, "models", []) or []) if getattr(m, "is_alive", True)]
        except Exception:
            alive_models = []
        returned = 0
        for model in to_return:
            try:
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
                if hasattr(root, "add_model"):
                    root.add_model(model)
                else:
                    root.models.append(model)
            except Exception:
                pass
            # Attempt to place the model near unit coherently
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
                    if pos is not None:
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

    def _apply_fleshcraft(self, unit, *, game=None, master_regenesist_choice: Optional[str] = None) -> int:
        try:
            roll = int(get_roll("D3"))
        except Exception:
            roll = 0
        choice = str(master_regenesist_choice or "").strip().upper()
        has_master_regenesist = self._unit_has_master_regenesist(unit)
        use_enhanced = bool(has_master_regenesist and choice == "ENHANCED")
        amount = max(0, int(roll or 0) + (3 if use_enhanced else 1))
        try:
            from ..utility.event_bus import append_dice
            player = self._unit_owner(unit)
            if player is not None:
                expr = "D3+3" if use_enhanced else "D3+1"
                append_dice(player, f"Fleshcraft return: {expr} = {amount}")
        except Exception:
            pass
        return self._return_destroyed_bodyguard_models(unit, amount=amount, game_map=getattr(game, "map", None))

    def _apply_sadistic_fulcrum(
        self,
        unit,
        *,
        sadistic_fulcrum_choice: Optional[str] = None,
        game=None,
        phase_name: str = "",
    ) -> bool:
        if str(phase_name or "").strip().upper() != "SHOOTING_PHASE":
            return False
        if unit is None or not self._unit_has_sadistic_fulcrum(unit):
            return False
        choice_key = str(sadistic_fulcrum_choice or "").strip()
        if not choice_key or choice_key.upper() == "NONE":
            return False
        army = self.army
        mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
        activate_fn = (
            getattr(mgr, "activate_skysplinter_sadistic_fulcrum", None)
            if mgr is not None
            else None
        )
        if not callable(activate_fn):
            return False
        transport_unit = self._resolve_unit_by_id(choice_key, game=game)
        if transport_unit is None:
            return False
        return bool(activate_fn(unit, transport_unit, game=game))

    def _apply_empowerment_effects(
        self,
        root,
        *,
        spec_keys: list[str],
        ability_names: list[str],
        choice_cache: dict,
        game,
        phase_name: str,
    ) -> bool:
        if root is None or game is None:
            return False
        if phase_name and self._empowered_this_phase(root, phase_name):
            return False
        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [root]
        for member in list(members or []):
            self._apply_empowered_markers(member, phase_name=phase_name, ability_names=ability_names)
            for spec_key in list(spec_keys or []):
                if spec_key == "HATRED_ETERNAL":
                    self._apply_hatred_eternal(member)
                elif spec_key == "LITHE_AGILITY":
                    self._apply_lithe_agility(member)
                elif spec_key == "BRIDES_OF_DEATH":
                    self._apply_brides_of_death(member)
                elif spec_key == "SCULPTOR_OF_TORMENTS":
                    self._apply_sculptor_of_torments(member)
                elif spec_key == "MASTER_OF_BLADES":
                    self._apply_master_of_blades(member)
                elif spec_key == "BATTLEFIELD_BUTCHERY":
                    self._apply_battlefield_butchery(member)
                elif spec_key == "ACROBATIC_GLADIATORS":
                    self._apply_acrobatic_gladiators(member)
                elif spec_key == "ARCHON_POISONED_TONGUE":
                    self._apply_archon_poisoned_tongue(
                        member,
                        choice_cache.get("archon_poisoned_tongue"),
                    )
                elif spec_key == "ASSASSINS_POISONS":
                    self._apply_assassins_poisons(member)
                elif spec_key == "DEADLY_RETINUE":
                    self._apply_deadly_retinue(member)
                elif spec_key == "DECAPITATING_STRIKES":
                    self._apply_decapitating_strikes(member)
                elif spec_key == "ELECTROMAGENTIC_CASCADE":
                    self._apply_electromagentic_cascade(member)
                elif spec_key == "ENGINE_OF_DESTRUCTION":
                    self._apply_engine_of_destruction(member)
                elif spec_key == "EXPERIMENTAL_ENHANCEMENTS":
                    self._apply_experimental_enhancements(
                        member,
                        choice_cache.get("experimental_enhancements"),
                    )
                elif spec_key == "GOADED_SAVAGERY":
                    self._apply_goaded_savagery(member)
                elif spec_key == "MACRO_STEROIDS":
                    self._apply_macro_steroids(member)
                elif spec_key == "MATCHLESS_SWIFTNESS":
                    self._apply_matchless_swiftness(member)
                elif spec_key == "MINDLESS_KILLING_MACHINES":
                    self._apply_mindless_killing_machines(member)
                elif spec_key == "NOWHERE_TO_RUN":
                    self._apply_nowhere_to_run(member)
                elif spec_key == "NOWHERE_TO_HIDE":
                    self._apply_nowhere_to_hide(member)
                elif spec_key == "AGONISING_SUPPRESSION":
                    self._apply_agonising_suppression(member)
                elif spec_key == "PAIN_PARASITE":
                    self._apply_pain_parasite(member)
                elif spec_key == "RAPID_DEPLOYMENT":
                    self._apply_rapid_deployment(member)
                elif spec_key == "SADISTIC_RAIDERS":
                    self._apply_sadistic_raiders(member)
                elif spec_key == "SHREDDING_FIRE":
                    self._apply_shredding_fire(member)
                elif spec_key == "SPLINTER_RACKS":
                    self._apply_splinter_racks(member)
                elif spec_key == "SWOOPING_DESCENT":
                    self._apply_swooping_descent(member)
                elif spec_key == "WINGED_STRIKE":
                    self._apply_winged_strike(member)
        # Fleshcraft returns models on the root unit (bodyguard only)
        for spec_key in list(spec_keys or []):
            if spec_key == "FLESHCRAFT":
                try:
                    self._apply_fleshcraft(
                        root,
                        game=game,
                        master_regenesist_choice=choice_cache.get("master_regenesist"),
                    )
                except Exception:
                    pass
            if spec_key == "FADE_AWAY":
                try:
                    self._apply_fade_away(root, game=game)
                except Exception:
                    pass
        self._apply_sadistic_fulcrum(
            root,
            sadistic_fulcrum_choice=choice_cache.get("sadistic_fulcrum_transport"),
            game=game,
            phase_name=phase_name,
        )
        return True

    def empower_unit_for_trigger(self, unit, *, trigger: str, game) -> bool:
        if not self._army_has_power_from_pain():
            return False
        if unit is None or game is None:
            return False
        if not bool(getattr(game, "is_authoritative", True)):
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return False
        if not self._unit_is_alive(root):
            return False
        phase_name = self._phase_name(game)
        if not phase_name:
            return False
        specs = self._applicable_pain_specs(root, trigger=trigger, game=game)
        if not specs:
            return False
        has_dark_vitality = self._unit_has_dark_vitality(root)
        allow_offboard = any(spec.key == "SWOOPING_DESCENT" for spec in specs)
        if not self._unit_on_battlefield(root) and not allow_offboard:
            return False
        if self._empowered_this_phase(root, phase_name):
            return False
        required_choices = []
        for spec in specs:
            if spec.key == "ARCHON_POISONED_TONGUE":
                required_choices.append("archon_poisoned_tongue")
            elif spec.key == "EXPERIMENTAL_ENHANCEMENTS":
                required_choices.append("experimental_enhancements")
            elif spec.key == "FLESHCRAFT" and self._unit_has_master_regenesist(root):
                required_choices.append("master_regenesist")
        if (
            str(phase_name or "").strip().upper() == "SHOOTING_PHASE"
            and self._unit_has_sadistic_fulcrum(root)
            and self._sadistic_fulcrum_transport_candidates_for_unit(root, game=game)
        ):
            required_choices.append("sadistic_fulcrum_transport")

        unit_id = get_entity_id(root)
        pending_key = self._pending_empowerment_key(unit_id, str(trigger or ""), phase_name)
        pending = self._pending_empowerments.get(pending_key)

        if required_choices:
            if pending is None:
                tokens_spent = False
                if not has_dark_vitality:
                    if int(self.tokens or 0) <= 0:
                        return False
                    if not self.spend_tokens(1, reason=f"Empower ({trigger})"):
                        return False
                    self._apply_pain_engine_refund_on_empower(root, game=game)
                    tokens_spent = True
                pending = {
                    "unit_id": unit_id,
                    "trigger": str(trigger or ""),
                    "phase_name": phase_name,
                    "spec_keys": [spec.key for spec in specs],
                    "ability_names": [spec.name for spec in specs],
                    "required_choices": list(required_choices),
                    "choices": {},
                    "tokens_spent": bool(tokens_spent),
                }
                self._pending_empowerments[pending_key] = pending
            else:
                pending.setdefault("spec_keys", [spec.key for spec in specs])
                pending.setdefault("ability_names", [spec.name for spec in specs])
                pending.setdefault("required_choices", list(required_choices))

            choices = dict(pending.get("choices", {}) or {})
            missing = [kind for kind in required_choices if kind not in choices]
            for kind in missing:
                if not self._pending_choice_request(game, pending_key, kind):
                    self._queue_choice_request(
                        game=game,
                        player=self._unit_owner(root),
                        unit_id=unit_id,
                        choice_kind=kind,
                        pending_key=pending_key,
                    )
            if missing:
                return False
            applied = self._finalize_pending_empowerment(pending_key, game=game)
            return bool(applied)

        if not has_dark_vitality:
            if int(self.tokens or 0) <= 0:
                return False
            if not self.spend_tokens(1, reason=f"Empower ({trigger})"):
                return False
            self._apply_pain_engine_refund_on_empower(root, game=game)
        applied = self._apply_empowerment_effects(
            root,
            spec_keys=[spec.key for spec in specs],
            ability_names=[spec.name for spec in specs],
            choice_cache={},
            game=game,
            phase_name=phase_name,
        )
        return bool(applied)

    def maybe_empower_unit_for_trigger(self, unit, *, trigger: str, game) -> bool:
        if not self._army_has_power_from_pain():
            return False
        if unit is None or game is None:
            return False
        applicable = self._applicable_pain_specs(unit, trigger=trigger, game=game)
        if not applicable:
            return False
        if self._unit_has_dark_vitality(unit):
            return bool(self.empower_unit_for_trigger(unit, trigger=trigger, game=game))
        if int(self.tokens or 0) <= 0:
            return False
        player = self._unit_owner(unit)
        if player is None:
            return False
        ctx = {
            "ability_name": "Power from Pain",
            "unit": getattr(unit, "name", "") or "",
            "trigger": trigger,
            "phase": self._phase_name(game),
            "pain_abilities": [spec.name for spec in applicable],
            "pain_tokens": int(self.tokens or 0),
            "pain_cost": 1,
            "unit_id": get_entity_id(unit),
        }
        queue_fn = getattr(game, "_queue_optional_ability_confirmation", None)
        if callable(queue_fn):
            message = (
                f"Empower {getattr(unit, 'name', 'Unit')} with Power from Pain for {trigger}?\n\n"
                f"Spend 1 Pain token to activate: {', '.join([spec.name for spec in applicable])}"
            )
            queue_fn(
                player=player,
                ability_key="power_from_pain_empower",
                ability_name="Power from Pain",
                message=message,
                context=ctx,
                payload={"unit_id": ctx.get("unit_id"), "trigger": trigger},
                instance_key=f"{ctx.get('unit_id') or ''}:{trigger}",
            )
        return False

    # ---------------- Stratagem Pain token support ----------------

    def stratagem_pain_token_cost(self, stratagem) -> int:
        if stratagem is None:
            return 0
        try:
            if str(getattr(stratagem, "faction_id", "") or "").strip().upper() != "DRU":
                return 0
        except Exception:
            return 0
        try:
            desc = str(getattr(stratagem, "description", "") or "").lower()
        except Exception:
            desc = ""
        if "pain token" not in desc:
            return 0
        # Best-effort parse: look for "spend X pain token"
        match = re.search(r"spend\s+(\d+)\s+pain\s+token", desc)
        if match:
            try:
                return max(0, int(match.group(1)))
            except Exception:
                return 1
        return 1

    def can_spend_pain_for_stratagem(self, stratagem) -> bool:
        cost = int(self.stratagem_pain_token_cost(stratagem) or 0)
        if cost <= 0:
            return True
        return int(self.tokens or 0) >= cost

    def spend_pain_for_stratagem(self, stratagem) -> bool:
        cost = int(self.stratagem_pain_token_cost(stratagem) or 0)
        if cost <= 0:
            return True
        return self.spend_tokens(cost, reason=f"Stratagem: {getattr(stratagem, 'name', '')}")
