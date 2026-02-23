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

    def gain_miracle_die(self, *, game=None, allow_reroll: bool = False, reason: str = "") -> int:
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
        self.gain_miracle_die(game=game, allow_reroll=False, reason="Battle round start")

    def on_unit_destroyed(self, unit, *, game=None, game_map=None, last_model=None) -> None:
        if unit is None or not self._army_has_rule():
            return
        if not self._unit_in_army(unit):
            return
        if not self._unit_has_rule(unit):
            return
        allow_reroll = self._litany_allows_reroll(destroyed_unit=unit, destroyed_model=last_model)
        self.gain_miracle_die(game=game, allow_reroll=allow_reroll, reason="Unit destroyed")

    def on_model_destroyed(self, unit, model, *, game=None, game_map=None) -> None:
        if unit is None or model is None or not self._army_has_rule():
            return
        if not self._unit_in_army(unit):
            return
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

    def _choose_chaplet_reroll_indices(self, *, unit, bearer_model, game, pool: list[int], max_rerolls: int) -> list[int]:
        if max_rerolls <= 0 or not pool:
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
                    max_rerolls=int(max_rerolls),
                    reason="Chaplet of Sacrifice",
                )
            except Exception:
                selection = None
            if selection is None:
                return []
            return self._normalize_chaplet_reroll_indices(selection, pool=list(pool), max_rerolls=int(max_rerolls))

        # Deterministic fallback: re-roll the lowest dice values (up to max), skip 6s.
        candidates = [idx for idx, die in enumerate(list(pool or [])) if int(die) < 6]
        candidates.sort(key=lambda idx: (int(pool[idx]), int(idx)))
        return list(candidates[: int(max_rerolls)])

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
