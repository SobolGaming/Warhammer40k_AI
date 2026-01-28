from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Optional

from ..utility.ability_support import ABILITY_POWER_FROM_PAIN, army_has_ability_id
from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id


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
        if unit is None:
            return False
        for ab in list(getattr(unit, "possible_abilities", []) or []):
            try:
                name = ab if isinstance(ab, str) else getattr(ab, "name", "")
            except Exception:
                name = ""
            if str(name or "").strip().lower() == "pain adept":
                return True
        return False

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
            print(f"Power from Pain: +{amount} token(s) ({reason})")
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
            print(f"Power from Pain: -{amount} token(s) ({reason})")
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

    def on_enemy_unit_destroyed(self, unit) -> None:
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
        player = self._unit_owner(unit)
        options = ["LETHAL HITS", "SUSTAINED HITS 1"]
        ctx = {
            "ability_name": "Archon of the Poisoned Tongue",
            "unit": getattr(unit, "name", "") or "",
            "options": list(options),
            "phase": self._phase_name(game),
        }
        choice = None
        try:
            if player is not None:
                choice = player._choose_optional_value("POWER_FROM_PAIN_ARCHON_POISONED_TONGUE", options, ctx)
        except Exception:
            choice = None
        if not choice:
            return "LETHAL"
        choice_norm = str(choice).strip().upper()
        if "SUSTAINED" in choice_norm:
            return "SUSTAINED"
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
        player = self._unit_owner(unit)
        options = ["ATTACKS 3", "ATTACKS 4 HAZARDOUS"]
        ctx = {
            "ability_name": "Experimental Enhancements",
            "unit": getattr(unit, "name", "") or "",
            "options": list(options),
            "phase": self._phase_name(game),
        }
        choice = None
        try:
            if player is not None:
                choice = player._choose_optional_value("POWER_FROM_PAIN_EXPERIMENTAL_ENHANCEMENTS", options, ctx)
        except Exception:
            choice = None
        if not choice:
            return "ATTACKS_3"
        choice_norm = str(choice).strip().upper()
        if "4" in choice_norm:
            return "ATTACKS_4_HAZARDOUS"
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
            print(f"Power from Pain: {root.name} removed into Strategic Reserves (Fade Away)")
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

    def _apply_fleshcraft(self, unit, *, game=None) -> int:
        try:
            roll = int(get_roll("D3"))
        except Exception:
            roll = 0
        amount = max(0, int(roll or 0) + 1)
        try:
            from ..utility.event_bus import append_dice
            player = self._unit_owner(unit)
            if player is not None:
                append_dice(player, f"Fleshcraft return: D3+1 = {amount}")
        except Exception:
            pass
        return self._return_destroyed_bodyguard_models(unit, amount=amount, game_map=getattr(game, "map", None))

    def empower_unit_for_trigger(self, unit, *, trigger: str, game) -> bool:
        if not self._army_has_power_from_pain():
            return False
        if unit is None or game is None:
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
        allow_offboard = any(spec.key == "SWOOPING_DESCENT" for spec in specs)
        if not self._unit_on_battlefield(root) and not allow_offboard:
            return False
        if self._empowered_this_phase(root, phase_name):
            return False
        if int(self.tokens or 0) <= 0:
            return False
        if not self.spend_tokens(1, reason=f"Empower ({trigger})"):
            return False
        ability_names = [spec.name for spec in specs]
        choice_cache = {}
        for spec in specs:
            if spec.key == "ARCHON_POISONED_TONGUE":
                choice_cache["archon_poisoned_tongue"] = self._choose_archon_poisoned_tongue(root, game=game)
            elif spec.key == "EXPERIMENTAL_ENHANCEMENTS":
                choice_cache["experimental_enhancements"] = self._choose_experimental_enhancements(root, game=game)
        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [root]
        for member in list(members or []):
            self._apply_empowered_markers(member, phase_name=phase_name, ability_names=ability_names)
            for spec in specs:
                if spec.key == "HATRED_ETERNAL":
                    self._apply_hatred_eternal(member)
                elif spec.key == "LITHE_AGILITY":
                    self._apply_lithe_agility(member)
                elif spec.key == "BRIDES_OF_DEATH":
                    self._apply_brides_of_death(member)
                elif spec.key == "SCULPTOR_OF_TORMENTS":
                    self._apply_sculptor_of_torments(member)
                elif spec.key == "MASTER_OF_BLADES":
                    self._apply_master_of_blades(member)
                elif spec.key == "BATTLEFIELD_BUTCHERY":
                    self._apply_battlefield_butchery(member)
                elif spec.key == "ACROBATIC_GLADIATORS":
                    self._apply_acrobatic_gladiators(member)
                elif spec.key == "ARCHON_POISONED_TONGUE":
                    self._apply_archon_poisoned_tongue(
                        member,
                        choice_cache.get("archon_poisoned_tongue"),
                    )
                elif spec.key == "ASSASSINS_POISONS":
                    self._apply_assassins_poisons(member)
                elif spec.key == "DEADLY_RETINUE":
                    self._apply_deadly_retinue(member)
                elif spec.key == "DECAPITATING_STRIKES":
                    self._apply_decapitating_strikes(member)
                elif spec.key == "ELECTROMAGENTIC_CASCADE":
                    self._apply_electromagentic_cascade(member)
                elif spec.key == "ENGINE_OF_DESTRUCTION":
                    self._apply_engine_of_destruction(member)
                elif spec.key == "EXPERIMENTAL_ENHANCEMENTS":
                    self._apply_experimental_enhancements(
                        member,
                        choice_cache.get("experimental_enhancements"),
                    )
                elif spec.key == "GOADED_SAVAGERY":
                    self._apply_goaded_savagery(member)
                elif spec.key == "MACRO_STEROIDS":
                    self._apply_macro_steroids(member)
                elif spec.key == "MATCHLESS_SWIFTNESS":
                    self._apply_matchless_swiftness(member)
                elif spec.key == "MINDLESS_KILLING_MACHINES":
                    self._apply_mindless_killing_machines(member)
                elif spec.key == "NOWHERE_TO_RUN":
                    self._apply_nowhere_to_run(member)
                elif spec.key == "NOWHERE_TO_HIDE":
                    self._apply_nowhere_to_hide(member)
                elif spec.key == "AGONISING_SUPPRESSION":
                    self._apply_agonising_suppression(member)
                elif spec.key == "PAIN_PARASITE":
                    self._apply_pain_parasite(member)
                elif spec.key == "RAPID_DEPLOYMENT":
                    self._apply_rapid_deployment(member)
                elif spec.key == "SADISTIC_RAIDERS":
                    self._apply_sadistic_raiders(member)
                elif spec.key == "SHREDDING_FIRE":
                    self._apply_shredding_fire(member)
                elif spec.key == "SPLINTER_RACKS":
                    self._apply_splinter_racks(member)
                elif spec.key == "SWOOPING_DESCENT":
                    self._apply_swooping_descent(member)
                elif spec.key == "WINGED_STRIKE":
                    self._apply_winged_strike(member)
        # Fleshcraft returns models on the root unit (bodyguard only)
        for spec in specs:
            if spec.key == "FLESHCRAFT":
                try:
                    self._apply_fleshcraft(root, game=game)
                except Exception:
                    pass
            if spec.key == "FADE_AWAY":
                try:
                    self._apply_fade_away(root, game=game)
                except Exception:
                    pass
        return True

    def maybe_empower_unit_for_trigger(self, unit, *, trigger: str, game) -> bool:
        if not self._army_has_power_from_pain():
            return False
        if unit is None or game is None:
            return False
        applicable = self._applicable_pain_specs(unit, trigger=trigger, game=game)
        if not applicable:
            return False
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
