from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable, Optional


class BlessingsTiming(Enum):
    START_OF_BATTLE_ROUND = "START_OF_BATTLE_ROUND"
    OTHER = "OTHER"


@dataclass(frozen=True)
class DiceRecipe:
    """
    A single dice consumption recipe, e.g.:
      - double 4+  => count=2, min_value=4, require_matching=True
      - triple 1+  => count=3, min_value=1, require_matching=True
    """

    count: int
    min_value: int
    require_matching: bool = True


@dataclass(frozen=True)
class BlessingDefinition:
    key: str
    name: str
    recipes: tuple[DiceRecipe, ...]
    short_effect: str


DEFAULT_BLESSINGS: tuple[BlessingDefinition, ...] = (
    BlessingDefinition(
        key="UNBRIDLED_BLOODLUST",
        name="Unbridled Bloodlust",
        recipes=(DiceRecipe(count=2, min_value=1),),
        short_effect="Re-roll Charge rolls (eligible units).",
    ),
    BlessingDefinition(
        key="RAGE_FUELLED_INVIGORATION",
        name="Rage-fuelled Invigoration",
        recipes=(DiceRecipe(count=2, min_value=2),),
        short_effect='Pile-in and Consolidation moves up to 6" (eligible units).',
    ),
    BlessingDefinition(
        key="TOTAL_CARNAGE",
        name="Total Carnage",
        recipes=(DiceRecipe(count=2, min_value=3),),
        short_effect="Fight on death on a 4+ when destroyed by melee (if not fought).",
    ),
    BlessingDefinition(
        key="MARTIAL_EXCELLENCE",
        name="Martial Excellence",
        recipes=(DiceRecipe(count=2, min_value=4), DiceRecipe(count=3, min_value=1)),
        short_effect="Melee gains Sustained Hits 1 (eligible units).",
    ),
    BlessingDefinition(
        key="WARP_BLADES",
        name="Warp Blades",
        recipes=(DiceRecipe(count=2, min_value=5), DiceRecipe(count=3, min_value=2)),
        short_effect="Melee gains Lethal Hits (eligible units).",
    ),
    BlessingDefinition(
        key="DECAPITATING_STRIKES",
        name="Decapitating Strikes",
        recipes=(DiceRecipe(count=2, min_value=6), DiceRecipe(count=3, min_value=3)),
        short_effect="Melee vs Infantry gains Devastating Wounds (eligible units).",
    ),
)


@dataclass
class BlessingsRollContext:
    """
    Represents a single Blessings roll event (start-of-round or 'additional roll').
    """

    timing: BlessingsTiming
    battle_round: int
    dice: list[int]
    rerolls_allowed: int
    rerolled_indices: list[int]
    max_activations: int
    # If True, this roll's activations do NOT count toward the baseline "up to 2" budget.
    counts_toward_baseline_limit: bool
    # Blessings already active this battle round (cannot be re-activated)
    already_active_keys: set[str]

    # If True, the special "Reborn in Blood" spend is available (triple 6).
    reborn_in_blood_available: bool = False


class BlessingsOfKhorneManager:
    """
    World Eaters army rule implementation.

    Notes:
    - This manager is intentionally UI-agnostic.
    - Human UI calls `create_roll_context(...)`, potentially re-rolls dice, then calls `apply_choice(...)`.
    """

    def __init__(self, *, definitions: Iterable[BlessingDefinition] = DEFAULT_BLESSINGS):
        self.definitions: dict[str, BlessingDefinition] = {d.key: d for d in definitions}
        self.active_blessing_keys: set[str] = set()
        self._active_battle_round: Optional[int] = None

        # Global resource: Bloodshed points (Icon of Khorne wargear ability; spent to add extra dice on any Blessings roll).
        #
        # NOTE: This is NOT "Blood Tithe" (which is a separate mechanic tied to the Khorne Daemonkin detachment).
        self.bloodshed_points: int = 0

        # Track how many baseline activations were used from the start-of-round roll (max 2)
        self._baseline_activations_used: int = 0

        # Deferred Total Carnage models (resolved after attacking unit finishes its attacks)
        self._pending_total_carnage: list[object] = []

    # ---------------- Lifecycle ----------------
    def on_battle_round_start(self, battle_round: int) -> None:
        # Blessings expire at end of battle round; clearing at start of the next is equivalent.
        self._active_battle_round = int(battle_round)
        self.active_blessing_keys.clear()
        self._baseline_activations_used = 0
        self._pending_total_carnage = []

    def is_active_this_battle_round(self, battle_round: int) -> bool:
        return self._active_battle_round == int(battle_round)

    # ---------------- Queries ----------------
    def is_blessing_active(self, key: str, *, battle_round: int) -> bool:
        if not self.is_active_this_battle_round(battle_round):
            return False
        return key in self.active_blessing_keys

    def _normalize_blessing_keys(self, keys: Iterable[str]) -> list[str]:
        out: list[str] = []
        for k in list(keys or []):
            kk = str(k).strip().upper()
            if not kk:
                continue
            if kk in self.definitions:
                if kk not in out:
                    out.append(kk)
                continue
            # Allow matching by name for convenience
            for dk, d in self.definitions.items():
                if d.name.strip().upper() == kk:
                    if dk not in out:
                        out.append(dk)
                    break
        return out

    def get_unit_specific_blessings(self, unit, *, battle_round: int) -> set[str]:
        if unit is None:
            return set()
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return set()
        try:
            br = int(sr.get("skulls_for_throne_battle_round", 0) or 0)
        except Exception:
            br = 0
        if int(battle_round) != br:
            return set()
        keys = self._normalize_blessing_keys(sr.get("skulls_for_throne_blessings", []) or [])
        return set(keys)

    def grant_unit_blessings(self, unit, *, blessing_keys: Iterable[str], battle_round: int) -> bool:
        if unit is None:
            return False
        keys = self._normalize_blessing_keys(blessing_keys)
        if not keys:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        try:
            br = int(sr.get("skulls_for_throne_battle_round", 0) or 0)
        except Exception:
            br = 0
        existing: list[str] = []
        if br == int(battle_round):
            existing = self._normalize_blessing_keys(sr.get("skulls_for_throne_blessings", []) or [])
        merged: list[str] = []
        for k in existing + list(keys):
            if k not in merged:
                merged.append(k)
        sr["skulls_for_throne_battle_round"] = int(battle_round)
        sr["skulls_for_throne_blessings"] = merged
        root.special_rules = sr
        return True

    def is_blessing_active_for_unit(self, key: str, unit, *, battle_round: int) -> bool:
        key_u = str(key or "").strip().upper()
        if not key_u:
            return False
        if self.is_blessing_active(key_u, battle_round=int(battle_round)):
            return True
        return key_u in self.get_unit_specific_blessings(unit, battle_round=int(battle_round))

    def favoured_of_khorne_rerolls_for_army(self, army) -> int:
        """
        Return the number of Blessings rerolls granted by Favoured of Khorne
        and any active Blood God's Favour selection. Bearer must be on the battlefield.
        """
        if army is None:
            return 0
        favoured = 0
        try:
            units = list(getattr(army, "units", []) or [])
        except Exception:
            units = []
        for u in units:
            try:
                if not (getattr(u, "deployed", False) and u.is_alive() and getattr(u, "reserve_status", "deployed") == "deployed"):
                    continue
            except Exception:
                continue
            try:
                sr = getattr(u, "special_rules", None)
                if isinstance(sr, dict) and int(sr.get("enhancement_favoured_of_khorne_rerolls", 0) or 0) >= 2:
                    favoured = max(favoured, 2)
            except Exception:
                pass
            try:
                enh = getattr(u, "enhancement", None)
                if enh is not None and str(getattr(enh, "name", "") or "").strip().lower() == "favoured of khorne":
                    favoured = max(favoured, 2)
            except Exception:
                continue
        extra = 0
        try:
            from .wrathful_presence import blood_gods_favour_rerolls_for_army
            extra = int(blood_gods_favour_rerolls_for_army(army) or 0)
        except Exception:
            extra = 0
        return max(favoured, extra)

    # ---------------- Roll + choose ----------------
    def create_roll_context(
        self,
        *,
        battle_round: int,
        timing: BlessingsTiming,
        base_dice_count: int = 8,
        extra_dice_from_idols: int = 0,
        rerolls_allowed: int = 0,
        max_activations: int,
        counts_toward_baseline_limit: bool,
        already_active_keys: Optional[set[str]] = None,
        roll_d6: Optional[Callable[[], int]] = None,
        reborn_in_blood_available: bool = False,
    ) -> BlessingsRollContext:
        if roll_d6 is None:
            from ..utility.dice import get_roll
            roll_d6 = lambda: int(get_roll("D6"))

        if already_active_keys is None:
            already_active_keys = set(self.active_blessing_keys)

        # Apply Bloodshed points (+N dice), then immediately spend them (reset to 0).
        bonus_from_bloodshed = int(self.bloodshed_points or 0)
        self.bloodshed_points = 0

        dice_count = int(base_dice_count) + int(bonus_from_bloodshed) + int(extra_dice_from_idols or 0)
        dice = [int(roll_d6()) for _ in range(max(0, dice_count))]

        return BlessingsRollContext(
            timing=timing,
            battle_round=int(battle_round),
            dice=dice,
            rerolls_allowed=int(rerolls_allowed),
            rerolled_indices=[],
            max_activations=int(max_activations),
            counts_toward_baseline_limit=bool(counts_toward_baseline_limit),
            already_active_keys=set(already_active_keys),
            reborn_in_blood_available=bool(reborn_in_blood_available),
        )

    def reroll_indices(self, ctx: BlessingsRollContext, indices: list[int], *, roll_d6: Optional[Callable[[], int]] = None) -> None:
        if roll_d6 is None:
            from ..utility.dice import get_roll
            roll_d6 = lambda: int(get_roll("D6"))

        unique = []
        for i in indices:
            ii = int(i)
            if 0 <= ii < len(ctx.dice) and ii not in unique:
                unique.append(ii)

        if len(unique) > ctx.rerolls_allowed:
            raise ValueError(f"Too many rerolls selected ({len(unique)}) - max {ctx.rerolls_allowed}")

        for ii in unique:
            ctx.dice[ii] = int(roll_d6())
        ctx.rerolled_indices = list(unique)

    def legal_blessings_for_ctx(self, ctx: BlessingsRollContext) -> list[str]:
        """Return blessing keys that are legal to activate given current dice (ignoring pairwise conflicts)."""
        keys: list[str] = []
        for k, d in self.definitions.items():
            if k in ctx.already_active_keys:
                continue
            if self._has_any_recipe(ctx.dice, d.recipes):
                keys.append(k)
        return keys

    def apply_choice(
        self,
        ctx: BlessingsRollContext,
        *,
        selected_blessing_keys: list[str],
        use_reborn_in_blood: bool = False,
    ) -> dict:
        """
        Apply the selected blessings for this roll.
        Returns a dict with:
          - activated: list[str] blessing keys activated
          - spent_indices: list[int] dice indices consumed
          - reborn_used: bool
        """
        if int(ctx.battle_round) != int(self._active_battle_round or ctx.battle_round):
            # If not yet initialized for this battle round, allow applying but implicitly activate for this BR.
            self.on_battle_round_start(ctx.battle_round)

        # Reborn in Blood is a special spend that replaces start-of-battle-round Blessings activations.
        if use_reborn_in_blood:
            if not ctx.reborn_in_blood_available:
                raise ValueError("Reborn in Blood is not available in this context.")
            # Must have triple 6 available
            triple = self._find_matching_group_indices(ctx.dice, count=3, min_value=6)
            if triple is None:
                raise ValueError("Reborn in Blood requires a triple 6.")
            # Reborn consumes the start-of-round Blessings activation opportunity entirely.
            if ctx.timing != BlessingsTiming.START_OF_BATTLE_ROUND:
                raise ValueError("Reborn in Blood can only be used at start of battle round.")
            if selected_blessing_keys:
                raise ValueError("Cannot activate Blessings when using Reborn in Blood for this roll.")
            # Do not modify active_blessing_keys.
            alloc = {"REBORN_IN_BLOOD": tuple(triple)}
            return {"activated": [], "spent_indices": list(triple), "reborn_used": True, "allocation": alloc}

        # Normalize and validate selection
        chosen: list[str] = []
        for k in selected_blessing_keys:
            kk = str(k).strip().upper()
            # Support users passing either already-normalized keys or names; enforce keys internally.
            if kk in self.definitions:
                key = kk
            else:
                # Try by name match
                key = None
                for dk, d in self.definitions.items():
                    if d.name.strip().lower() == str(k).strip().lower():
                        key = dk
                        break
                if key is None:
                    raise ValueError(f"Unknown Blessing: {k}")
            if key in ctx.already_active_keys:
                raise ValueError(f"Blessing already active this battle round: {self.definitions[key].name}")
            if key not in chosen:
                chosen.append(key)

        if len(chosen) > int(ctx.max_activations):
            raise ValueError(f"Too many Blessings selected ({len(chosen)}) - max {ctx.max_activations}")

        # Enforce baseline limit for start-of-round roll
        if ctx.counts_toward_baseline_limit:
            if (self._baseline_activations_used + len(chosen)) > 2:
                raise ValueError("Baseline Blessings activation limit exceeded (max 2 per battle round).")

        # Find a feasible dice assignment for the chosen blessings.
        allocation = self._allocate_dice_for_blessings(ctx.dice, chosen)
        if allocation is None:
            raise ValueError("Selected Blessings cannot be activated with the available dice.")

        spent_indices = sorted({i for indices in allocation.values() for i in indices})

        # Activate
        for k in chosen:
            self.active_blessing_keys.add(k)
        if ctx.counts_toward_baseline_limit:
            self._baseline_activations_used += len(chosen)

        return {"activated": chosen, "spent_indices": spent_indices, "reborn_used": False, "allocation": allocation}

    def preview_choice(
        self,
        ctx: BlessingsRollContext,
        *,
        selected_blessing_keys: list[str],
        use_reborn_in_blood: bool = False,
    ) -> dict:
        """
        Like apply_choice, but does NOT mutate manager state.

        Returns:
          - ok: bool
          - error: str
          - spent_indices: list[int]
        """
        # Snapshot state
        snap_active = set(self.active_blessing_keys)
        snap_round = self._active_battle_round
        snap_used = int(self._baseline_activations_used)
        snap_bloodshed = int(self.bloodshed_points)
        snap_pending = list(self._pending_total_carnage)
        try:
            res = self.apply_choice(
                ctx,
                selected_blessing_keys=list(selected_blessing_keys),
                use_reborn_in_blood=bool(use_reborn_in_blood),
            )
            alloc = res.get("allocation") or {}
            # allocation values are tuples of indices; expose a stable, JSON-ish shape for UI
            pretty_alloc = {}
            try:
                for k, idxs in dict(alloc).items():
                    pretty_alloc[str(k)] = [int(i) for i in list(idxs or [])]
            except Exception:
                pretty_alloc = {}
            return {
                "ok": True,
                "error": "",
                "spent_indices": list(res.get("spent_indices", [])),
                "allocation": pretty_alloc,
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "spent_indices": [], "allocation": {}}
        finally:
            self.active_blessing_keys = snap_active
            self._active_battle_round = snap_round
            self._baseline_activations_used = snap_used
            self.bloodshed_points = snap_bloodshed
            self._pending_total_carnage = snap_pending

    # ---------------- Network decision helpers ----------------
    def _army_has_blessings(self, army) -> bool:
        if army is None:
            return False
        try:
            from ..utility.ability_support import ABILITY_BLESSINGS_OF_KHORNE, army_has_ability_id
        except Exception:
            return False
        if not army_has_ability_id(army, ABILITY_BLESSINGS_OF_KHORNE):
            return False
        for unit in list(getattr(army, "units", []) or []):
            try:
                if unit.attached_unit_has_blessings_of_khorne():
                    return True
            except Exception:
                continue
        return False

    def serialize_ctx_payload(self, ctx: BlessingsRollContext) -> dict:
        if ctx is None:
            return {}
        timing = getattr(ctx, "timing", None)
        if hasattr(timing, "name"):
            timing_val = timing.name
        else:
            timing_val = str(timing or "")
        return {
            "timing": timing_val,
            "battle_round": int(getattr(ctx, "battle_round", 0) or 0),
            "dice": list(getattr(ctx, "dice", []) or []),
            "rerolls_allowed": int(getattr(ctx, "rerolls_allowed", 0) or 0),
            "rerolled_indices": list(getattr(ctx, "rerolled_indices", []) or []),
            "max_activations": int(getattr(ctx, "max_activations", 0) or 0),
            "counts_toward_baseline_limit": bool(getattr(ctx, "counts_toward_baseline_limit", False)),
            "already_active_keys": list(getattr(ctx, "already_active_keys", set()) or []),
            "reborn_in_blood_available": bool(getattr(ctx, "reborn_in_blood_available", False)),
        }

    def deserialize_ctx_payload(self, ctx_data: dict) -> BlessingsRollContext:
        timing_val = ctx_data.get("timing")
        if isinstance(timing_val, BlessingsTiming):
            timing = timing_val
        else:
            timing_name = str(timing_val or "").strip()
            try:
                timing = BlessingsTiming[timing_name]
            except Exception:
                try:
                    timing = BlessingsTiming(timing_name)
                except Exception as exc:
                    raise RuntimeError("Blessings timing invalid.") from exc
        return BlessingsRollContext(
            timing=timing,
            battle_round=int(ctx_data.get("battle_round", 0) or 0),
            dice=list(ctx_data.get("dice", []) or []),
            rerolls_allowed=int(ctx_data.get("rerolls_allowed", 0) or 0),
            rerolled_indices=list(ctx_data.get("rerolled_indices", []) or []),
            max_activations=int(ctx_data.get("max_activations", 0) or 0),
            counts_toward_baseline_limit=bool(ctx_data.get("counts_toward_baseline_limit", False)),
            already_active_keys=set(ctx_data.get("already_active_keys", []) or []),
            reborn_in_blood_available=bool(ctx_data.get("reborn_in_blood_available", False)),
        )

    def build_start_of_round_request(self, army, *, battle_round: int, game=None):
        if army is None:
            return None
        if not self._army_has_blessings(army):
            return None
        player = getattr(army, "player", None)
        if player is None:
            return None
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_BLESSINGS
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.entity_ids import get_entity_id
            from .blessings_of_khorne import BlessingsTiming
        except Exception:
            return None

        rerolls_allowed = 0
        try:
            rerolls_allowed = int(self.favoured_of_khorne_rerolls_for_army(army) or 0)
        except Exception:
            rerolls_allowed = 0

        idol_bonus = 0
        try:
            for u in list(getattr(army, "units", []) or []):
                if not (getattr(u, "deployed", False) and u.is_alive() and getattr(u, "reserve_status", "deployed") == "deployed"):
                    continue
                found, _ = u._find_ability_with_patterns(["idol of blessed blood", "idol of the blessed blood"])
                if found:
                    idol_bonus += 1
        except Exception:
            idol_bonus = 0

        reborn_available = False
        try:
            for u in list(getattr(army, "units", []) or []):
                found, _ = u._find_ability_with_patterns(["reborn in blood"])
                if found and (not u.is_alive()):
                    reborn_available = True
                    break
        except Exception:
            reborn_available = False

        roll_fn = None
        if game is not None:
            try:
                rng = getattr(game, "random_source", None)
                if rng is not None and hasattr(rng, "randint"):
                    roll_fn = lambda: int(rng.randint(1, 6))
            except Exception:
                roll_fn = None

        ctx = self.create_roll_context(
            battle_round=int(battle_round),
            timing=BlessingsTiming.START_OF_BATTLE_ROUND,
            extra_dice_from_idols=idol_bonus,
            rerolls_allowed=rerolls_allowed,
            max_activations=2,
            counts_toward_baseline_limit=True,
            already_active_keys=set(),
            reborn_in_blood_available=reborn_available,
            roll_d6=roll_fn,
        )

        army_id = get_entity_id(army)
        req = DecisionRequest.create(
            DECISION_CHOOSE_BLESSINGS,
            "Select Blessings of Khorne.",
            player_id=getattr(player, "id", None),
            options=[DecisionOption.create("Confirm", payload={"army_id": army_id})],
            context={"army_id": army_id, "ctx": self.serialize_ctx_payload(ctx)},
        )
        if game is not None:
            request_fn = getattr(game, "request_decision", None)
            if callable(request_fn):
                request_fn(req)
        return req

    # ---------------- Total Carnage deferred resolution ----------------
    def queue_total_carnage_model(self, model_obj: object) -> None:
        self._pending_total_carnage.append(model_obj)

    def resolve_total_carnage_queue(self, *, owning_unit, game_map) -> None:
        """
        Resolve queued Total Carnage models after an attacker finishes resolving attacks.
        Best-effort: models are already removed from the unit; we still perform fight-on-death attacks using the model object.
        """
        if not self._pending_total_carnage:
            return
        pending = list(self._pending_total_carnage)
        self._pending_total_carnage = []

        from ..utility.dice import get_roll
        for model in pending:
            try:
                roll = int(get_roll("D6"))
            except Exception:
                roll = 1
            if roll < 4:
                continue
            try:
                owning_unit._try_fight_on_death(model=model, game_map=game_map)
            except Exception:
                continue

    # ---------------- Internals: dice matching & allocation ----------------
    def _has_any_recipe(self, dice: list[int], recipes: Iterable[DiceRecipe]) -> bool:
        for r in recipes:
            if self._find_matching_group_indices(dice, count=r.count, min_value=r.min_value) is not None:
                return True
        return False

    def _find_matching_group_indices(self, dice: list[int], *, count: int, min_value: int) -> Optional[tuple[int, ...]]:
        """
        Matching interpretation:
        - Need `count` dice with the SAME face value v, where v >= min_value.
        """
        # Count occurrences per face value
        by_val: dict[int, list[int]] = {}
        for idx, v in enumerate(list(dice or [])):
            try:
                vv = int(v)
            except Exception:
                continue
            by_val.setdefault(vv, []).append(idx)
        for v in sorted(by_val.keys()):
            if v < int(min_value):
                continue
            idxs = by_val[v]
            if len(idxs) >= int(count):
                return tuple(idxs[: int(count)])
        return None

    def _allocate_dice_for_blessings(self, dice: list[int], blessing_keys: list[str]) -> Optional[dict[str, tuple[int, ...]]]:
        """
        Backtracking allocation:
        - For each blessing, pick one recipe and reserve its matching dice indices.
        - No die index may be used twice.
        """
        # Order blessings by "hardness" (higher required min_value first, then count)
        def _hardness(k: str) -> tuple[int, int, int]:
            d = self.definitions[k]
            # Hardest recipe first
            best = max((r.min_value, r.count) for r in d.recipes)
            return (best[0], best[1], len(d.recipes))

        keys = sorted(list(blessing_keys), key=_hardness, reverse=True)

        used: set[int] = set()
        out: dict[str, tuple[int, ...]] = {}

        def _search(i: int) -> bool:
            if i >= len(keys):
                return True
            k = keys[i]
            d = self.definitions[k]
            # Try recipes in descending strictness
            recipes = sorted(list(d.recipes), key=lambda r: (r.min_value, r.count), reverse=True)
            for r in recipes:
                # Find any matching group, considering used indices
                candidates = self._all_matching_groups(dice, count=r.count, min_value=r.min_value, excluded=used)
                for group in candidates:
                    for idx in group:
                        used.add(idx)
                    out[k] = tuple(group)
                    if _search(i + 1):
                        return True
                    # backtrack
                    for idx in group:
                        used.remove(idx)
                    out.pop(k, None)
            return False

        return out if _search(0) else None

    def _all_matching_groups(
        self,
        dice: list[int],
        *,
        count: int,
        min_value: int,
        excluded: set[int],
    ) -> list[tuple[int, ...]]:
        by_val: dict[int, list[int]] = {}
        for idx, v in enumerate(list(dice or [])):
            if idx in excluded:
                continue
            try:
                vv = int(v)
            except Exception:
                continue
            by_val.setdefault(vv, []).append(idx)
        out: list[tuple[int, ...]] = []
        for v in sorted(by_val.keys()):
            if v < int(min_value):
                continue
            idxs = by_val[v]
            if len(idxs) >= int(count):
                out.append(tuple(idxs[: int(count)]))
        return out
