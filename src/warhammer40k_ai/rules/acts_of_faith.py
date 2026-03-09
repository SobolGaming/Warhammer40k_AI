from __future__ import annotations

import re
from typing import Optional, Tuple

from ..utility.ability_support import ABILITY_ACTS_OF_FAITH, army_has_ability_id
from ..utility.dice import get_roll, get_dice_roll
from ..utility.event_bus import append_dice
from ..utility.entity_ids import get_entity_id
from ..utility.aura_utils import (
    unit_within_range_of_unit,
    distance_between_models_bases_3d,
)


class ActsOfFaithManager:
    """
    Adepta Sororitas army rule: Acts of Faith.

    - Maintain a shared Miracle dice pool.
    - Gain dice at battle round start and when Adepta Sororitas units are destroyed.
    - Allow each unit to perform one Act of Faith per phase (one die substitution).
    """

    def __init__(self, army=None):
        self.army = army
        self.miracle_dice: list[int] = []
        self._used_in_phase: dict[str, tuple[str, int]] = {}

    def _army_has_rule(self) -> bool:
        if self.army is None:
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "AS":
            return False
        if army_has_ability_id(self.army, ABILITY_ACTS_OF_FAITH):
            return True
        if not faction_id:
            for unit in list(getattr(self.army, "units", []) or []):
                if self._unit_has_rule(unit):
                    return True
        return False

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        try:
            return unit.get_parent_army() is self.army
        except Exception:
            return False

    @staticmethod
    def _unit_id(unit) -> str:
        if unit is None:
            return ""
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        return get_entity_id(root)

    @staticmethod
    def _unit_root(unit):
        if unit is None:
            return None
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        return root

    @staticmethod
    def _phase_key(game) -> str:
        try:
            phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            phase = ""
        try:
            player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            player = None
        try:
            pid = get_entity_id(player)
        except Exception:
            pid = ""
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        if not phase:
            phase = "UNKNOWN"
        return f"{turn}:{pid}:{phase}"

    def _unit_has_rule(self, unit) -> bool:
        if unit is None:
            return False
        try:
            for ab in list(getattr(unit, "possible_abilities", []) or []):
                if str(getattr(ab, "name", "") or "").strip().lower() == "acts of faith":
                    return True
        except Exception:
            pass
        try:
            if unit.has_any_keyword("ADEPTA SORORITAS"):
                return True
        except Exception:
            pass
        return False

    def _unit_has_litany_of_deeds(self, unit) -> bool:
        if unit is None:
            return False
        try:
            for ab in list(getattr(unit, "possible_abilities", []) or []):
                name = str(getattr(ab, "name", "") or "").strip().lower()
                if name == "litany of deeds":
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _norm_name_fragment(value: str) -> str:
        text = str(value or "")
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _unit_has_ability_named(self, unit, ability_name: str) -> bool:
        if unit is None:
            return False
        target = self._norm_name_fragment(ability_name)
        if not target:
            return False
        try:
            for ab in list(getattr(unit, "possible_abilities", []) or []):
                name = self._norm_name_fragment(getattr(ab, "name", ""))
                if name == target:
                    return True
        except Exception:
            return False
        return False

    def _solemn_procession_forces_battle_round_six(self) -> bool:
        if self.army is None:
            return False
        seen_root_ids: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            root_id = self._unit_id(root)
            if root_id:
                if root_id in seen_root_ids:
                    continue
                seen_root_ids.add(root_id)
            if not self._unit_on_battlefield(root):
                continue
            if self._unit_has_ability_named(root, "Solemn Procession"):
                return True
        return False

    def _model_matches_name(self, model, target_name: str) -> bool:
        if model is None:
            return False
        target = self._norm_name_fragment(target_name)
        if not target:
            return False
        model_name = self._norm_name_fragment(getattr(model, "name", ""))
        if not model_name:
            return False
        if target in model_name:
            return True
        target_tokens = set(target.split())
        if target_tokens and target_tokens.issubset(set(model_name.split())):
            return True
        return False

    def _unit_contains_named_alive_model(self, unit, target_name: str) -> bool:
        if unit is None:
            return False
        contains_named = getattr(unit, "_unit_contains_model_named", None)
        if callable(contains_named):
            try:
                return bool(contains_named(target_name))
            except Exception:
                pass
        for model in list(getattr(unit, "models", []) or []):
            if not self._model_is_alive(model):
                continue
            if self._model_matches_name(model, target_name):
                return True
        return False

    def _iter_recount_the_deeds_eligible_leaders(self, attached_root) -> list:
        if attached_root is None or not self._unit_in_army(attached_root):
            return []
        try:
            leaders = list(getattr(attached_root, "attached_leaders", []) or [])
        except Exception:
            leaders = []
        eligible = []
        for leader in leaders:
            if leader is None:
                continue
            if not self._unit_in_army(leader):
                continue
            if getattr(leader, "attached_to", None) is not attached_root:
                continue
            if not self._unit_has_ability_named(leader, "Recount the Deeds of the Saints"):
                continue
            if not self._unit_contains_named_alive_model(leader, "Agathae Dolan"):
                continue
            eligible.append(leader)
        return eligible

    def _maybe_trigger_recount_the_deeds_enemy_unit_destroyed(
        self,
        *,
        unit,
        destroyed_by_unit,
        game=None,
    ) -> None:
        if unit is None or destroyed_by_unit is None:
            return
        target_root = self._unit_root(unit)
        attacker_root = self._unit_root(destroyed_by_unit)
        if target_root is None or attacker_root is None:
            return
        if self._unit_in_army(target_root):
            return
        if not self._unit_in_army(attacker_root):
            return
        if not self._iter_recount_the_deeds_eligible_leaders(attacker_root):
            return
        self.gain_miracle_die(game=game, allow_reroll=False, reason="Recount the Deeds of the Saints")

    def _maybe_trigger_recount_the_deeds_agathae_destroyed(
        self,
        *,
        unit,
        model,
        game=None,
    ) -> None:
        if unit is None or model is None:
            return
        if not self._unit_has_ability_named(unit, "Recount the Deeds of the Saints"):
            return
        if not self._model_matches_name(model, "Agathae Dolan"):
            return
        if getattr(model, "_recount_the_deeds_triggered", False):
            return
        try:
            setattr(model, "_recount_the_deeds_triggered", True)
        except Exception:
            pass

        try:
            extra = int(get_roll("D3") or 0)
        except Exception:
            extra = 0
        if extra <= 0:
            return
        allow_reroll = self._litany_allows_reroll(destroyed_unit=unit, destroyed_model=model)
        for _ in range(int(extra)):
            self.gain_miracle_die(
                game=game,
                allow_reroll=allow_reroll,
                reason="Recount the Deeds of the Saints",
            )

    @staticmethod
    def _cherub_max_uses_for_ability(ability) -> int:
        name = ""
        desc = ""
        try:
            name = str(getattr(ability, "name", "") or "").strip().lower()
        except Exception:
            name = ""
        try:
            desc = str(getattr(ability, "description", "") or "")
        except Exception:
            desc = ""

        if name == "cherubs":
            return 2
        if name == "cherub":
            return 1

        text = f"{name} {desc}".lower()
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return 0
        if (
            "after this unit has performed an act of faith" in text
            and "you gain 1 miracle dice" in text
        ):
            if "twice per battle" in text:
                return 2
            if "once per battle" in text:
                return 1
        return 0

    def _cherub_max_uses_for_unit(self, unit) -> int:
        root = self._unit_root(unit)
        if root is None:
            return 0
        max_uses = 0
        try:
            abilities = list(getattr(root, "possible_abilities", []) or [])
        except Exception:
            abilities = []
        for ability in abilities:
            uses = self._cherub_max_uses_for_ability(ability)
            if uses > max_uses:
                max_uses = uses
        return int(max_uses)

    def _maybe_trigger_cherub_miracle_die(self, unit, *, game=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        max_uses = self._cherub_max_uses_for_unit(root)
        if max_uses <= 0:
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        try:
            used = int(sr.get("acts_of_faith_cherub_uses", 0) or 0)
        except Exception:
            used = 0
        if used >= max_uses:
            return False

        reason = "Cherubs" if max_uses > 1 else "Cherub"
        self.gain_miracle_die(game=game, allow_reroll=False, reason=reason)
        sr["acts_of_faith_cherub_uses"] = int(used + 1)
        root.special_rules = sr
        return True

    def _iter_litany_sources(self) -> list:
        sources = []
        for unit in list(getattr(self.army, "units", []) or []):
            try:
                if not self._unit_has_litany_of_deeds(unit):
                    continue
            except Exception:
                continue
            try:
                if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                    continue
            except Exception:
                continue
            try:
                if not bool(getattr(unit, "deployed", True)):
                    continue
            except Exception:
                pass
            try:
                if bool(getattr(unit, "is_embarked", False)):
                    continue
            except Exception:
                pass
            sources.append(unit)
        return sources

    def _model_within_range_of_unit(self, source_unit, target_model, radius: float) -> bool:
        try:
            r = float(radius)
        except Exception:
            return False
        if r < 0:
            return False
        if source_unit is None or target_model is None:
            return False
        try:
            models = list(source_unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(source_unit, "models", []) or [])
        for sm in models:
            try:
                if not getattr(sm, "is_alive", True):
                    continue
            except Exception:
                continue
            try:
                if distance_between_models_bases_3d(sm, target_model) <= r + 1e-6:
                    return True
            except Exception:
                continue
        return False

    def _litany_allows_reroll(self, destroyed_unit=None, destroyed_model=None) -> bool:
        sources = self._iter_litany_sources()
        if not sources:
            return False
        for source in sources:
            try:
                if destroyed_model is not None and self._model_within_range_of_unit(source, destroyed_model, 12.0):
                    return True
            except Exception:
                pass
            try:
                if destroyed_unit is not None and unit_within_range_of_unit(source, destroyed_unit, 12.0):
                    return True
            except Exception:
                pass
        return False

    def can_use_act_of_faith(self, unit, *, game=None) -> bool:
        if not self._army_has_rule():
            return False
        if not self._unit_in_army(unit):
            return False
        if not self._unit_has_rule(unit):
            return False
        try:
            if bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            pass
        if not self.miracle_dice:
            return False
        phase_key = self._phase_key(game)
        uid = self._unit_id(unit)
        max_acts = 1
        try:
            mgr = getattr(self.army, "adepta_sororitas_detachments", None) if self.army is not None else None
            max_fn = getattr(mgr, "sacred_rites_max_acts_of_faith_per_phase", None) if mgr is not None else None
            if callable(max_fn):
                max_acts = max(1, int(max_fn(unit) or 1))
        except Exception:
            max_acts = 1
        try:
            from ..utility.aura_effects import get_aura_max_acts_of_faith_per_phase

            aura_max = int(
                get_aura_max_acts_of_faith_per_phase(
                    unit,
                    game_map=getattr(game, "map", None),
                )
                or 1
            )
            max_acts = max(int(max_acts), max(1, int(aura_max)))
        except Exception:
            pass

        used_phase = ""
        used_count = 0
        entry = self._used_in_phase.get(uid)
        if isinstance(entry, tuple):
            used_phase = str(entry[0] or "")
            try:
                used_count = int(entry[1] or 0)
            except Exception:
                used_count = 0
        elif entry is not None:
            used_phase = str(entry or "")
            used_count = 1

        if phase_key and used_phase == phase_key and used_count >= int(max_acts):
            return False
        return True

    def _mark_used(self, unit, *, game=None) -> None:
        uid = self._unit_id(unit)
        phase_key = self._phase_key(game)
        if uid:
            used_count = 0
            current = self._used_in_phase.get(uid)
            if isinstance(current, tuple) and str(current[0] or "") == phase_key:
                try:
                    used_count = int(current[1] or 0)
                except Exception:
                    used_count = 0
            elif current is not None and str(current or "") == phase_key:
                used_count = 1
            self._used_in_phase[uid] = (phase_key, int(used_count + 1))

    def _choose_miracle_die(self, unit, *, roll_type: str, dice_count: int, die_faces: int, game=None, needed=None) -> Optional[int]:
        if not self.can_use_act_of_faith(unit, game=game):
            return None
        pool = list(self.miracle_dice)
        if not pool:
            return None
        player = getattr(self.army, "player", None) if self.army is not None else None
        provider = getattr(getattr(game, "map", None), "miracle_dice_provider", None) if game is not None else None
        if callable(provider):
            try:
                chosen = provider(
                    player=player,
                    unit=unit,
                    roll_type=str(roll_type or ""),
                    dice_count=int(dice_count or 1),
                    die_faces=int(die_faces or 6),
                    pool=list(pool),
                    needed=needed,
                )
            except Exception:
                chosen = None
            try:
                chosen_val = int(chosen)
            except Exception:
                chosen_val = None
            if chosen_val is not None and chosen_val in pool:
                return chosen_val
            return None
        return None

    def maybe_use_miracle_die(
        self,
        unit,
        *,
        roll_type: str,
        dice_count: int,
        die_faces: int,
        game=None,
        needed=None,
    ) -> Optional[int]:
        """
        Prompt for a Miracle die selection and consume it if chosen.
        Returns the chosen value, or None if no Miracle die is used.
        """
        chosen = None
        try:
            chosen = self._choose_miracle_die(
                unit,
                roll_type=roll_type,
                dice_count=int(dice_count or 1),
                die_faces=int(die_faces or 6),
                game=game,
                needed=needed,
            )
        except Exception:
            chosen = None
        if chosen is None:
            return None
        if self._consume_miracle_die(unit, int(chosen), roll_type=roll_type, game=game):
            return int(chosen)
        return None

    def _consume_miracle_die(self, unit, value: int, *, roll_type: str, game=None) -> bool:
        try:
            idx = self.miracle_dice.index(int(value))
        except Exception:
            return False
        self.miracle_dice.pop(idx)
        self._mark_used(unit, game=game)
        try:
            rt = str(roll_type or "").strip().lower()
            if rt not in {"advance", "charge", "hit", "wound", "save", "damage"}:
                player = getattr(self.army, "player", None)
                if player is not None:
                    append_dice(player, f"Miracle die used ({roll_type}): {int(value)}")
        except Exception:
            pass
        try:
            self._maybe_trigger_cherub_miracle_die(unit, game=game)
        except Exception:
            pass
        return True

    def resolve_roll(
        self,
        unit,
        *,
        roll_type: str,
        dice_count: int = 1,
        die_faces: int = 6,
        modifier: int = 0,
        game=None,
        needed=None,
    ) -> Tuple[int, list[int], bool]:
        """
        Roll dice for a unit, optionally substituting a Miracle die.

        Returns: (total_value, dice_list, miracle_used)
        """
        try:
            count = max(1, int(dice_count or 1))
        except Exception:
            count = 1
        try:
            faces = max(1, int(die_faces or 6))
        except Exception:
            faces = 6
        try:
            mod = int(modifier or 0)
        except Exception:
            mod = 0

        chosen = self._choose_miracle_die(
            unit,
            roll_type=roll_type,
            dice_count=count,
            die_faces=faces,
            game=game,
            needed=needed,
        )
        if chosen is not None and self._consume_miracle_die(unit, int(chosen), roll_type=roll_type, game=game):
            if count == 1:
                dice = [int(chosen)]
            else:
                other = [get_dice_roll(faces) for _ in range(count - 1)]
                dice = [int(chosen)] + other
            total = int(sum(dice) + mod)
            return total, dice, True

        dice = [get_dice_roll(faces) for _ in range(count)]
        total = int(sum(dice) + mod)
        return total, dice, False

    def _maybe_reroll_miracle_die(self, value: int, *, allow_reroll: bool, game=None) -> int:
        if not allow_reroll:
            return int(value or 0)
        player = getattr(self.army, "player", None) if self.army is not None else None
        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None) if game is not None else None
        if callable(provider):
            try:
                want = bool(provider(
                    player=player,
                    unit=None,
                    roll_type="miracle",
                    value=int(value or 0),
                    dice=None,
                    reason="Litany of Deeds",
                ))
            except Exception:
                want = False
            if not want:
                return int(value or 0)
        return int(get_roll("D6") or 0)

    def gain_miracle_die(
        self,
        *,
        game=None,
        allow_reroll: bool = False,
        reason: str = "",
        battle_round_start: bool = False,
    ) -> int:
        if bool(battle_round_start) and self._solemn_procession_forces_battle_round_six():
            value = 6
        else:
            value = int(get_roll("D6") or 0)
            value = self._maybe_reroll_miracle_die(value, allow_reroll=allow_reroll, game=game)
        self.miracle_dice.append(int(value))
        try:
            player = getattr(self.army, "player", None)
            if player is not None:
                note = f"Miracle die gained: {int(value)}"
                if reason:
                    note = f"{note} ({reason})"
                append_dice(player, note)
        except Exception:
            pass
        return int(value)

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self._army_has_rule():
            return
        self.gain_miracle_die(
            game=game,
            allow_reroll=False,
            reason="Battle round start",
            battle_round_start=True,
        )

    def on_unit_destroyed(
        self,
        unit,
        *,
        game=None,
        game_map=None,
        last_model=None,
        destroyed_by_unit=None,
        destroyed_by_model=None,
        destroyed_by_weapon_profile=None,
    ) -> None:
        if unit is None or not self._army_has_rule():
            return
        if self._unit_in_army(unit):
            if not self._unit_has_rule(unit):
                return
            allow_reroll = self._litany_allows_reroll(destroyed_unit=unit, destroyed_model=last_model)
            self.gain_miracle_die(game=game, allow_reroll=allow_reroll, reason="Unit destroyed")
            return
        self._maybe_trigger_blade_of_saint_ellynor(
            unit=unit,
            destroyed_by_unit=destroyed_by_unit,
            destroyed_by_model=destroyed_by_model,
            destroyed_by_weapon_profile=destroyed_by_weapon_profile,
            game=game,
        )
        self._maybe_trigger_recount_the_deeds_enemy_unit_destroyed(
            unit=unit,
            destroyed_by_unit=destroyed_by_unit,
            game=game,
        )
        self._maybe_trigger_psalm_of_righteous_judgement(
            unit=unit,
            destroyed_by_unit=destroyed_by_unit,
            game=game,
        )

    def on_model_destroyed(self, unit, model, *, game=None, game_map=None) -> None:
        if unit is None or model is None or not self._army_has_rule():
            return
        if not self._unit_in_army(unit):
            return
        self._maybe_trigger_recount_the_deeds_agathae_destroyed(unit=unit, model=model, game=game)
        enh = getattr(unit, "enhancement", None)
        name = ""
        enh_id = ""
        try:
            name = str(getattr(enh, "name", "") or "").strip().lower()
        except Exception:
            name = ""
        try:
            enh_id = str(getattr(enh, "id", "") or "").strip()
        except Exception:
            enh_id = ""
        if not (name == "saintly example" or enh_id == "000008470002"):
            return
        if getattr(model, "_saintly_example_triggered", False):
            return
        try:
            setattr(model, "_saintly_example_triggered", True)
        except Exception:
            pass

        try:
            extra = int(get_roll("D3") or 0)
        except Exception:
            extra = 0
        if extra <= 0:
            return
        allow_reroll = self._litany_allows_reroll(destroyed_unit=unit, destroyed_model=model)
        for _ in range(int(extra)):
            self.gain_miracle_die(game=game, allow_reroll=allow_reroll, reason="Saintly Example")

    def _is_hallowed_martyrs(self) -> bool:
        if self.army is None:
            return False
        mgr = getattr(self.army, "adepta_sororitas_detachments", None)
        checker = getattr(mgr, "is_hallowed_martyrs", None) if mgr is not None else None
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                return False
        return False

    def _is_army_of_faith(self) -> bool:
        if self.army is None:
            return False
        mgr = getattr(self.army, "adepta_sororitas_detachments", None)
        checker = getattr(mgr, "is_army_of_faith", None) if mgr is not None else None
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                return False
        return False

    def _is_bringers_of_flame(self) -> bool:
        if self.army is None:
            return False
        mgr = getattr(self.army, "adepta_sororitas_detachments", None)
        checker = getattr(mgr, "is_bringers_of_flame", None) if mgr is not None else None
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                return False
        return False

    def _is_penitent_host(self) -> bool:
        if self.army is None:
            return False
        mgr = getattr(self.army, "adepta_sororitas_detachments", None)
        checker = getattr(mgr, "is_penitent_host", None) if mgr is not None else None
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                return False
        return False

    @staticmethod
    def _unit_special_rules(unit) -> dict:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        return sr

    def _unit_has_special_rule(self, unit, key: str) -> bool:
        if unit is None or not key:
            return False
        sr = self._unit_special_rules(unit)
        return bool(sr.get(key, False))

    def _get_enhancement_bearer_model(self, unit):
        if unit is None:
            return None
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        bearer = get_bearer() if callable(get_bearer) else None
        if bearer is None:
            models = list(getattr(unit, "models", []) or [])
            for model in models:
                if self._model_is_alive(model):
                    bearer = model
                    break
        if bearer is None or not self._model_is_alive(bearer):
            return None
        return bearer

    @staticmethod
    def _is_melee_weapon_profile(weapon_profile) -> bool:
        if weapon_profile is None:
            return False
        parent = getattr(weapon_profile, "parent_wargear", None)
        is_melee = getattr(parent, "is_melee", None) if parent is not None else None
        if not callable(is_melee):
            return False
        try:
            return bool(is_melee())
        except Exception:
            return False

    def _blade_state_key(self, game=None) -> str:
        return f"blade_of_saint_ellynor:{self._phase_key(game)}"

    def on_fight_unit_selected(self, unit, *, game=None, selecting_player=None) -> None:
        if not self._army_has_rule() or unit is None:
            return
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return
        if self._is_bringers_of_flame():
            self._maybe_apply_righteous_rage(root, game=game, selecting_player=selecting_player)
        if not self._is_army_of_faith():
            return
        if not self._unit_has_special_rule(root, "enhancement_blade_of_saint_ellynor"):
            return
        bearer = self._get_enhancement_bearer_model(root)
        if bearer is None:
            return
        state = {
            "phase_key": self._phase_key(game),
            "bearer_model_id": str(get_entity_id(bearer) or ""),
            "awarded": False,
        }
        sr = self._unit_special_rules(root)
        sr = dict(sr)
        sr["enhancement_blade_of_saint_ellynor_active_fight"] = state
        root.special_rules = sr

    def _maybe_trigger_blade_of_saint_ellynor(
        self,
        *,
        unit,
        destroyed_by_unit,
        destroyed_by_model,
        destroyed_by_weapon_profile,
        game=None,
    ) -> None:
        if not self._is_army_of_faith():
            return
        if unit is None or destroyed_by_unit is None or destroyed_by_model is None:
            return
        if not self._is_melee_weapon_profile(destroyed_by_weapon_profile):
            return
        attacker_root = self._unit_root(destroyed_by_unit)
        if attacker_root is None or not self._unit_in_army(attacker_root):
            return
        target_root = self._unit_root(unit)
        if target_root is None:
            return
        if self._unit_in_army(target_root):
            return
        sr = self._unit_special_rules(attacker_root)
        if not bool(sr.get("enhancement_blade_of_saint_ellynor", False)):
            return
        active = sr.get("enhancement_blade_of_saint_ellynor_active_fight")
        if not isinstance(active, dict):
            return
        phase_key = str(active.get("phase_key", "") or "")
        if phase_key != self._phase_key(game):
            return
        if bool(active.get("awarded", False)):
            return

        expected_bearer_id = str(active.get("bearer_model_id", "") or "")
        if not expected_bearer_id:
            expected_bearer_id = str(sr.get("enhancement_blade_of_saint_ellynor_bearer_model_id", "") or "")
        actual_bearer_id = str(get_entity_id(destroyed_by_model) or "")
        if expected_bearer_id and actual_bearer_id and expected_bearer_id != actual_bearer_id:
            return

        self.gain_miracle_die(game=game, allow_reroll=False, reason="Blade of Saint Ellynor")
        updated = dict(active)
        updated["awarded"] = True
        sr = dict(sr)
        sr["enhancement_blade_of_saint_ellynor_active_fight"] = updated
        attacker_root.special_rules = sr

    def _maybe_trigger_psalm_of_righteous_judgement(
        self,
        *,
        unit,
        destroyed_by_unit,
        game=None,
    ) -> None:
        if not self._is_penitent_host():
            return
        if unit is None or destroyed_by_unit is None:
            return
        if not self.miracle_dice:
            return

        target_root = self._unit_root(unit)
        attacker_root = self._unit_root(destroyed_by_unit)
        if target_root is None or attacker_root is None:
            return
        if self._unit_in_army(target_root):
            return
        if not self._unit_in_army(attacker_root):
            return

        as_mgr = getattr(self.army, "adepta_sororitas_detachments", None) if self.army is not None else None
        is_penitent_fn = getattr(as_mgr, "unit_is_penitent", None) if as_mgr is not None else None
        if not callable(is_penitent_fn) or not bool(is_penitent_fn(attacker_root)):
            return

        sources = []
        seen_ids: set[str] = set()
        for source_unit in list(getattr(self.army, "units", []) or []):
            if source_unit is None:
                continue
            source_id = str(getattr(source_unit, "id", getattr(source_unit, "_id", "")) or "")
            if source_id and source_id in seen_ids:
                continue
            sr = self._unit_special_rules(source_unit)
            if not bool(sr.get("enhancement_psalm_of_righteous_judgement", False)):
                continue
            if not self._unit_on_battlefield(self._unit_root(source_unit)):
                continue
            bearer = self._get_enhancement_bearer_model(source_unit)
            if bearer is None:
                continue
            if source_id:
                seen_ids.add(source_id)
            sources.append(source_unit)
        if not sources:
            return
        sources = sorted(
            list(sources),
            key=lambda source_unit: str(getattr(source_unit, "id", getattr(source_unit, "_id", "")) or ""),
        )

        for source_unit in sources:
            if not self.miracle_dice:
                break
            source_sr = self._unit_special_rules(source_unit)
            try:
                discard_count = int(source_sr.get("enhancement_psalm_of_righteous_judgement_discard_count", 1) or 1)
            except (TypeError, ValueError):
                discard_count = 1
            if discard_count <= 0:
                continue
            max_select = min(int(discard_count), len(self.miracle_dice))
            if max_select <= 0:
                continue
            bearer_model = self._get_enhancement_bearer_model(source_unit)
            if bearer_model is None:
                continue
            chosen_indices = self._choose_miracle_pool_indices(
                unit=source_unit,
                bearer_model=bearer_model,
                game=game,
                pool=list(self.miracle_dice),
                max_select=int(max_select),
                reason="Psalm of Righteous Judgement",
                skip_sixes=True,
            )
            if not chosen_indices:
                continue
            discarded = self._discard_miracle_dice_by_indices(
                self.miracle_dice,
                chosen_indices[: int(discard_count)],
            )
            if not discarded:
                continue
            try:
                gained_value = int(source_sr.get("enhancement_psalm_of_righteous_judgement_gained_value", 6) or 6)
            except (TypeError, ValueError):
                gained_value = 6
            gained_value = int(max(1, min(6, gained_value)))
            self.miracle_dice.append(int(gained_value))
            player = getattr(self.army, "player", None) if self.army is not None else None
            if player is not None:
                append_dice(
                    player,
                    (
                        "Psalm of Righteous Judgement: discarded Miracle dice "
                        f"{discarded} to gain Miracle die {int(gained_value)}."
                    ),
                )

    @staticmethod
    def _model_is_alive(model) -> bool:
        if model is None:
            return False
        alive = getattr(model, "is_alive", None)
        if callable(alive):
            try:
                return bool(alive())
            except Exception:
                return False
        if alive is not None:
            return bool(alive)
        try:
            return int(getattr(model, "wounds", 0) or 0) > 0
        except Exception:
            return False

    @staticmethod
    def _unit_on_battlefield(unit) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            try:
                if not bool(is_alive()):
                    return False
            except Exception:
                return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        try:
            if bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            pass
        try:
            in_reserves = getattr(unit, "is_in_reserves", None)
            if callable(in_reserves) and bool(in_reserves()):
                return False
        except Exception:
            return False
        return True

    @staticmethod
    def _normalize_chaplet_reroll_indices(selection, *, pool: list[int], max_rerolls: int) -> list[int]:
        if max_rerolls <= 0 or not pool:
            return []
        selected: list[int] = []
        used: set[int] = set()

        def _add_index(index: int) -> None:
            if len(selected) >= int(max_rerolls):
                return
            if index < 0 or index >= len(pool):
                return
            if index in used:
                return
            used.add(index)
            selected.append(int(index))

        if isinstance(selection, dict):
            indices = selection.get("indices", selection.get("dice_indices", ()))
            values = selection.get("values", selection.get("dice_values", ()))
            for idx in list(indices or []):
                try:
                    _add_index(int(idx))
                except Exception:
                    continue
            for raw_value in list(values or []):
                try:
                    value = int(raw_value)
                except Exception:
                    continue
                for idx, die in enumerate(pool):
                    if idx in used:
                        continue
                    if int(die) == int(value):
                        _add_index(idx)
                        break
        else:
            if isinstance(selection, (int, str)):
                raw_iter = [selection]
            else:
                try:
                    raw_iter = list(selection or [])
                except Exception:
                    raw_iter = []
            for raw_value in raw_iter:
                try:
                    value = int(raw_value)
                except Exception:
                    continue
                for idx, die in enumerate(pool):
                    if idx in used:
                        continue
                    if int(die) == int(value):
                        _add_index(idx)
                        break

        selected.sort()
        return selected

    def _choose_miracle_pool_indices(
        self,
        *,
        unit,
        bearer_model,
        game,
        pool: list[int],
        max_select: int,
        reason: str,
        skip_sixes: bool = True,
    ) -> list[int]:
        if max_select <= 0 or not pool:
            return []
        player = getattr(self.army, "player", None) if self.army is not None else None
        provider = getattr(getattr(game, "map", None), "miracle_dice_pool_reroll_provider", None) if game is not None else None
        if callable(provider):
            try:
                selection = provider(
                    player=player,
                    unit=unit,
                    model=bearer_model,
                    pool=list(pool),
                    max_rerolls=int(max_select),
                    reason=str(reason or ""),
                )
            except Exception:
                selection = None
            if selection is None:
                return []
            return self._normalize_chaplet_reroll_indices(selection, pool=list(pool), max_rerolls=int(max_select))

        # Deterministic fallback: select the lowest dice values up to limit.
        candidates = []
        for idx, die in enumerate(list(pool or [])):
            try:
                val = int(die)
            except Exception:
                continue
            if skip_sixes and val >= 6:
                continue
            candidates.append(idx)
        candidates.sort(key=lambda idx: (int(pool[idx]), int(idx)))
        return list(candidates[: int(max_select)])

    @staticmethod
    def _discard_miracle_dice_by_indices(pool: list[int], indices: list[int]) -> list[int]:
        discarded: list[int] = []
        for idx in sorted(list(indices or []), reverse=True):
            if idx < 0 or idx >= len(pool):
                continue
            try:
                val = int(pool[idx] or 0)
            except Exception:
                val = 0
            discarded.append(val)
            del pool[idx]
        discarded.reverse()
        return discarded

    def _choose_chaplet_reroll_indices(self, *, unit, bearer_model, game, pool: list[int], max_rerolls: int) -> list[int]:
        return self._choose_miracle_pool_indices(
            unit=unit,
            bearer_model=bearer_model,
            game=game,
            pool=list(pool or []),
            max_select=int(max_rerolls or 0),
            reason="Chaplet of Sacrifice",
            skip_sixes=True,
        )

    def _maybe_apply_righteous_rage(self, unit, *, game=None, selecting_player=None) -> None:
        if unit is None or not self._unit_has_special_rule(unit, "enhancement_righteous_rage"):
            return
        owner = getattr(self.army, "player", None) if self.army is not None else None
        if selecting_player is not None and owner is not None and selecting_player is not owner:
            return
        bearer = self._get_enhancement_bearer_model(unit)
        if bearer is None:
            return
        if not self.miracle_dice:
            return
        sr = self._unit_special_rules(unit)
        try:
            max_discard = int(sr.get("enhancement_righteous_rage_max_discard", 3) or 3)
        except Exception:
            max_discard = 3
        max_discard = max(0, min(int(max_discard), len(self.miracle_dice)))
        if max_discard <= 0:
            return
        chosen_indices = self._choose_miracle_pool_indices(
            unit=unit,
            bearer_model=bearer,
            game=game,
            pool=list(self.miracle_dice),
            max_select=int(max_discard),
            reason="Righteous Rage",
            skip_sixes=True,
        )
        if not chosen_indices:
            return
        discarded = self._discard_miracle_dice_by_indices(self.miracle_dice, chosen_indices)
        discard_count = len(discarded)
        if discard_count <= 0:
            return
        try:
            bonus_per_die = int(sr.get("enhancement_righteous_rage_bonus_per_discard", 1) or 1)
        except Exception:
            bonus_per_die = 1
        bonus_per_die = max(1, int(bonus_per_die))
        bonus_to_add = int(discard_count) * int(bonus_per_die)
        try:
            current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        except Exception:
            current_turn = 0
        try:
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            phase_name = ""
        if not phase_name:
            phase_name = "FIGHT_PHASE"
        owner_id = str(get_entity_id(owner) or getattr(owner, "id", "")) if owner is not None else ""
        try:
            existing_bonus = int(sr.get("enhancement_righteous_rage_bonus", 0) or 0)
        except Exception:
            existing_bonus = 0
        try:
            existing_turn = int(sr.get("enhancement_righteous_rage_turn", 0) or 0)
        except Exception:
            existing_turn = 0
        existing_phase = str(sr.get("enhancement_righteous_rage_expires_phase", "") or "").strip().upper()
        existing_owner = str(sr.get("enhancement_righteous_rage_owner", "") or "")
        if (
            existing_turn
            and current_turn
            and existing_turn != current_turn
        ) or (existing_phase and phase_name and existing_phase != phase_name) or (
            existing_owner and owner_id and existing_owner != owner_id
        ):
            existing_bonus = 0
        sr = dict(sr)
        sr["enhancement_righteous_rage_bonus"] = int(max(0, int(existing_bonus) + int(bonus_to_add)))
        sr["enhancement_righteous_rage_turn"] = int(current_turn)
        sr["enhancement_righteous_rage_owner"] = str(owner_id)
        sr["enhancement_righteous_rage_expires_phase"] = str(phase_name)
        unit.special_rules = sr
        try:
            if owner is not None:
                append_dice(
                    owner,
                    (
                        "Righteous Rage: discarded Miracle dice "
                        f"{discarded} for +{int(bonus_to_add)} Attacks/Strength this phase"
                    ),
                )
        except Exception:
            pass

    def _maybe_apply_manual_of_saint_griselda(self, unit, *, game=None) -> None:
        if unit is None or not self._unit_has_special_rule(unit, "enhancement_manual_of_saint_griselda"):
            return
        bearer = self._get_enhancement_bearer_model(unit)
        if bearer is None:
            return
        if not self.miracle_dice:
            return
        sr = self._unit_special_rules(unit)
        try:
            max_discard = int(sr.get("enhancement_manual_of_saint_griselda_max_discard", 2) or 2)
        except Exception:
            max_discard = 2
        try:
            result_cap = int(sr.get("enhancement_manual_of_saint_griselda_result_value_max", 6) or 6)
        except Exception:
            result_cap = 6
        max_discard = max(0, min(int(max_discard), len(self.miracle_dice)))
        if max_discard <= 0:
            return
        chosen_indices = self._choose_miracle_pool_indices(
            unit=unit,
            bearer_model=bearer,
            game=game,
            pool=list(self.miracle_dice),
            max_select=int(max_discard),
            reason="Manual of Saint Griselda",
            skip_sixes=True,
        )
        if not chosen_indices:
            return
        discarded = self._discard_miracle_dice_by_indices(self.miracle_dice, chosen_indices)
        if not discarded:
            return
        total = 0
        for value in list(discarded or []):
            try:
                total += int(value or 0)
            except Exception:
                continue
        if total <= 0:
            return
        new_value = int(min(int(max(1, result_cap)), int(total)))
        self.miracle_dice.append(int(new_value))
        try:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            if owner is not None:
                append_dice(
                    owner,
                    (
                        "Manual of Saint Griselda: discarded Miracle dice "
                        f"{discarded} to add Miracle die {int(new_value)}"
                    ),
                )
        except Exception:
            pass

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if not self._army_has_rule():
            return
        is_army_of_faith = self._is_army_of_faith()
        is_bringers_of_flame = self._is_bringers_of_flame()
        if not is_army_of_faith and not is_bringers_of_flame:
            return
        if self.army is None:
            return
        owner = getattr(self.army, "player", None)
        if owner is None:
            return
        if player is not None and player is not owner:
            return
        if game is not None:
            try:
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                phase_name = ""
            if phase_name and phase_name != "COMMAND_PHASE":
                return
            try:
                current = getattr(game, "get_current_player", lambda: None)()
            except Exception:
                current = None
            if current is not None and current is not owner:
                return

        units = list(getattr(self.army, "units", []) or [])
        try:
            units = sorted(units, key=lambda unit: str(get_entity_id(unit) or ""))
        except Exception:
            units = list(units)

        for unit in units:
            if unit is None:
                continue
            if not self._unit_in_army(unit):
                continue
            if not self._unit_on_battlefield(unit):
                continue
            if is_army_of_faith and self._unit_has_special_rule(unit, "enhancement_litanies_of_faith"):
                bearer = self._get_enhancement_bearer_model(unit)
                if bearer is not None:
                    pass_test_fn = getattr(unit, "pass_leadership_check_for_model", None)
                    if callable(pass_test_fn):
                        try:
                            passed = bool(pass_test_fn(bearer))
                        except Exception:
                            passed = False
                        if passed:
                            self.gain_miracle_die(game=game, allow_reroll=False, reason="Litanies of Faith")
            if is_bringers_of_flame and self._unit_has_special_rule(unit, "enhancement_manual_of_saint_griselda"):
                self._maybe_apply_manual_of_saint_griselda(unit, game=game)

    def on_command_phase_end(self, *, game=None, player=None) -> None:
        if not self._army_has_rule():
            return
        if not self._is_hallowed_martyrs():
            return
        if self.army is None:
            return
        owner = getattr(self.army, "player", None)
        if player is not None and owner is not None and player is not owner:
            return
        if game is not None:
            try:
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                phase_name = ""
            if phase_name and phase_name != "COMMAND_PHASE":
                return
            try:
                current = getattr(game, "get_current_player", lambda: None)()
            except Exception:
                current = None
            if current is not None and owner is not None and current is not owner:
                return

        if not self.miracle_dice:
            return

        units = list(getattr(self.army, "units", []) or [])
        try:
            units = sorted(units, key=lambda u: str(get_entity_id(u) or ""))
        except Exception:
            units = list(units)

        for unit in units:
            if unit is None:
                continue
            if not self._unit_in_army(unit):
                continue
            if not self._unit_on_battlefield(unit):
                continue

            enh = getattr(unit, "enhancement", None)
            name = str(getattr(enh, "name", "") or "").strip().lower()
            enh_id = str(getattr(enh, "id", "") or "").strip()
            if not (name == "chaplet of sacrifice" or enh_id == "000008470004"):
                continue

            get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            if bearer is None:
                models = list(getattr(unit, "models", []) or [])
                for m in models:
                    if self._model_is_alive(m):
                        bearer = m
                        break
            if bearer is None:
                continue
            if not self._model_is_alive(bearer):
                continue

            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            is_below_starting = False
            try:
                is_below_starting = bool(getattr(root, "is_below_starting_strength", lambda: False)())
            except Exception:
                is_below_starting = False
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            try:
                max_rerolls = int(
                    sr.get(
                        "enhancement_chaplet_of_sacrifice_max_rerolls_damaged"
                        if is_below_starting
                        else "enhancement_chaplet_of_sacrifice_max_rerolls",
                        3 if is_below_starting else 1,
                    )
                    or (3 if is_below_starting else 1)
                )
            except Exception:
                max_rerolls = 3 if is_below_starting else 1
            if max_rerolls <= 0:
                continue
            if not self.miracle_dice:
                continue
            max_rerolls = min(int(max_rerolls), len(self.miracle_dice))
            selected_indices = self._choose_chaplet_reroll_indices(
                unit=unit,
                bearer_model=bearer,
                game=game,
                pool=list(self.miracle_dice),
                max_rerolls=int(max_rerolls),
            )
            if not selected_indices:
                continue
            for idx in list(selected_indices):
                if idx < 0 or idx >= len(self.miracle_dice):
                    continue
                before = int(self.miracle_dice[idx] or 0)
                after = int(get_roll("D6") or 0)
                self.miracle_dice[idx] = int(after)
                try:
                    if owner is not None:
                        append_dice(
                            owner,
                            f"Chaplet of Sacrifice: re-rolled Miracle die {int(before)} -> {int(after)}.",
                        )
                except Exception:
                    pass
