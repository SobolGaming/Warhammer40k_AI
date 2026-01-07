from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Optional

from ..utility.ability_support import ABILITY_POWER_FROM_PAIN, army_has_ability_id
from ..utility.dice import get_roll


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


SUPPORTED_PAIN_ABILITIES: dict[str, PainAbilitySpec] = {
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
    "sculptor of torments": PainAbilitySpec(
        key="SCULPTOR_OF_TORMENTS",
        name="Sculptor of Torments",
        triggers=(PainTriggerSpec(TRIGGER_FIGHT, "FIGHT_PHASE", requires_active_turn=False),),
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
                usable.append(spec)
                break
        return usable

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
            pn = getattr(player, "name", "")
            append_dice(pn, f"Pain Adept roll: {roll}")
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
                append_dice(player.name, f"Fleshcraft return: D3+1 = {amount}")
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
        if not self._unit_on_battlefield(root):
            return False
        if not self._unit_is_alive(root):
            return False
        phase_name = self._phase_name(game)
        if not phase_name:
            return False
        if self._empowered_this_phase(root, phase_name):
            return False
        specs = self._applicable_pain_specs(root, trigger=trigger, game=game)
        if not specs:
            return False
        if int(self.tokens or 0) <= 0:
            return False
        if not self.spend_tokens(1, reason=f"Empower ({trigger})"):
            return False
        ability_names = [spec.name for spec in specs]
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
        # Fleshcraft returns models on the root unit (bodyguard only)
        for spec in specs:
            if spec.key == "FLESHCRAFT":
                try:
                    self._apply_fleshcraft(root, game=game)
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
        }
        try:
            should = bool(getattr(player, "_should_use_optional_ability", lambda *_a, **_k: False)("POWER_FROM_PAIN", ctx))
        except Exception:
            should = False
        if not should:
            return False
        return self.empower_unit_for_trigger(unit, trigger=trigger, game=game)

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
