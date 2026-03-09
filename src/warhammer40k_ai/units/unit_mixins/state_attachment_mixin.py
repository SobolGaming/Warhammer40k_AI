"""Auto-extracted Unit mixin methods from unit.py."""

from ._common import *
import logging
logger = logging.getLogger(__name__)

_NAMED_UNIT_LIMIT_WORD_TO_INT = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

_NAMED_UNIT_INCLUSION_LIMIT_RE = re.compile(
    r"\byour\s+army\s+cannot\s+include\s+more\s+than\s+"
    r"(?P<limit>\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
    r"(?P<unit>.+?)\s+units?\b",
    re.IGNORECASE,
)

_INSPIRING_COMMANDER_OC_SET_RE = re.compile(
    r"if\s+you\s+include\s+this\s+model\s+in\s+your\s+army\s+until\s+the\s+end\s+of\s+the\s+battle\s+"
    r"non\s+character\s+models\s+in\s+(?P<units>.+?)\s+units?\s+from\s+your\s+army\s+"
    r"have\s+an\s+objective\s+control\s+characteristic\s+of\s+(?P<value>\d+)\s+"
    r"while\s+they\s+are\s+not\s+battle\s+shocked",
    re.IGNORECASE,
)

_BODYGUARD_TWO_LEADER_RE = re.compile(
    r"if\s+this\s+unit\s+has\s+a\s+starting\s+strength\s+of\s+(?P<min>\d+).*?"
    r"attach\s+up\s+to\s+(?:2|two)\s+leader\s+units?\s+to\s+it\s+instead\s+of\s+one",
    re.IGNORECASE,
)
_BODYGUARD_NO_DUPLICATE_LEADERS_RE = re.compile(
    r"\bnot\s+duplicates?\b",
    re.IGNORECASE,
)
_BODYGUARD_TRANSPORT_EMBARK_OVERRIDE_RE = re.compile(
    r"while this (?:model|unit) is (?:leading|joined to) a unit "
    r"it can embark within any transport that (?:its bodyguard unit|that unit) can embark within",
    re.IGNORECASE,
)
_MODEL_EMBARKING_WITHIN_TRANSPORTS_RE = re.compile(
    r"this model can embark within friendly (?P<faction>[a-z0-9 ]+) transport models "
    r"that can transport (?P<keyword>[a-z0-9 ]+) models "
    r"when doing so it takes up the space of (?P<slots>\d+) infantry models",
    re.IGNORECASE,
)

_MASTERS_OF_THE_MAELSTROM_TARGET_UNIT_NAMES = {
    "chosen",
    "legionaries",
    "red corsairs raiders",
}
_HURON_BLACKHEART_DATASHEET_ID = "000000925"
_HEROES_OF_ULTRAMAR_TARGET_UNIT_NAMES = {
    "assault intercessor squad",
    "bladeguard veteran squad",
    "intercessor squad",
    "sternguard veteran squad",
}
_CAPTAIN_TITUS_DATASHEET_ID = "000004187"


def _normalize_unit_name_for_rules(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _split_named_unit_list(value: str) -> list[str]:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return []
    parts = re.split(r"\s*(?:,|\band\b|\bor\b)\s*", text, flags=re.IGNORECASE)
    return [re.sub(r"\s+", " ", part).strip() for part in parts if str(part or "").strip()]


class StateAttachmentMixin:
    def add_model(self, model: Model) -> None:
        assert model not in self.models
        model.set_parent_unit(self)
        self.models.append(model)
        army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
        player = getattr(army, "player", None) if army is not None else None
        game = getattr(player, "game", None) if player is not None else None
        registry = getattr(game, "entity_registry", None) if game is not None else None
        if registry is not None:
            registry.register(model, kind="model")
            registry.register_many(getattr(model, "wargear", []) or [], kind="wargear")
        # Invalidate ability cache since unit composition changed
        self._invalidate_ability_cache()
        self.update_coherency()

    def update_coherency(self) -> None:
        # Coherency thresholds depend on the number of models in the unit.
        # Use alive model count so casualties adjust the requirement correctly.
        models = list(getattr(self, "models", []) or [])
        try:
            if self is self.get_attached_unit_root():
                models = list(self._get_bodyguard_support_models() or [])
        except Exception:
            pass
        alive_count = len([
            m for m in models
            if getattr(m, 'is_alive', True) and not getattr(m, "_pending_placement", False)
        ])
        if alive_count <= 1:
            self.coherency_distance = 2.0
            self.required_neighbors = 0
        elif alive_count >= 7:
            self.coherency_distance = 2.0
            self.required_neighbors = 2
        else:
            self.coherency_distance = 2.0
            self.required_neighbors = 1

    def initialize_round(self) -> None:
        """Reset round-tracked variables to default state."""
        self.round_state = UnitRoundState()
        try:
            self._death_ecstasy_pending_models = []
        except Exception:
            pass
        try:
            self._beautiful_death_pending_models = []
        except Exception:
            pass
        try:
            self._berserk_fugue_pending_models = []
        except Exception:
            pass
        # Check status effects expiration (with safe defaults)
        for status_effect in list(getattr(self, "status_effects", []) or []):
            try:
                status_effect.check_expiration(self)
            except Exception:
                # If status effect check fails, just continue
                # This prevents crashes from incomplete status effect implementations
                pass
        
        # Reset reserves arrival flag
        self.arrived_from_reserves_this_turn = False
        # Reset edge-touch Strategic Reserves restriction (only applies on the turn the unit arrives).
        try:
            setattr(self, "_reserves_edge_touch_this_turn", False)
        except Exception:
            pass

        # Reset per-model "counts as having shot via Firing Deck" flags.
        # This is model-scoped (not unit-scoped) to support the core rule that only the selected embarked
        # models count as having shot when their weapons are used via a transport's Firing Deck.
        for m in list(getattr(self, "models", []) or []):
            try:
                setattr(m, "_shot_via_firing_deck_this_round", False)
            except Exception:
                pass

        # Clear any stale firing-deck virtual wargear bookkeeping.
        try:
            self.clear_firing_deck_virtual_wargear()
        except Exception:
            pass

    def is_max_health(self) -> Tuple[bool, Optional[Model]]:
        """
        Check if the unit is at full health.

        Returns:
            Tuple[bool, Optional[Model]]: A tuple containing:
                - A boolean indicating if the unit is at full health
                - The first damaged model found, or None if all models are at full health
        """
        for model in self.models:
            if not model.is_max_health:
                return False, model
        return True, None

    def is_below_half_strength(self) -> bool:
        """
        Check if the unit is below half its starting strength for Battle-Shock purposes.
        
        For multi-model units: Check if current model count is less than half starting count
        For single-model units: Check if current wounds are less than half starting wounds
        
        Returns:
            bool: True if unit is below half strength and should take Battle-Shock tests
        """
        # Attached Leaders are not evaluated separately; the Attached unit is treated as one unit.
        try:
            if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                return False
        except Exception:
            pass

        # Compute effective starting/current strength across attached members (bodyguard + leaders).
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [self]

        starting_models = 0
        current_models = 0
        starting_wounds = 0
        current_wounds = 0

        for u in members:
            try:
                starting_models += int(getattr(u, "starting_model_count", len(getattr(u, "models", []) or [])))
            except Exception:
                starting_models += 0
            try:
                current_models += int(len(getattr(u, "models", []) or []))
            except Exception:
                current_models += 0
            try:
                starting_wounds += int(getattr(u, "starting_total_wounds", 0))
            except Exception:
                pass
            try:
                for m in (getattr(u, "models", []) or []):
                    if getattr(m, "is_alive", True):
                        current_wounds += int(getattr(m, "wounds", 0))
            except Exception:
                pass

        # If destroyed, definitely below half strength
        if current_models <= 0:
            return True

        if starting_models > 1:
            # Multi-model unit: check model count
            return current_models < (starting_models / 2.0)

        # Single-model unit: check wounds
        if starting_wounds <= 0:
            return False
        return current_wounds < (starting_wounds / 2.0)

    def is_below_starting_strength(self) -> bool:
        """
        Check if the unit is Below Starting Strength (distinct from Below Half-strength).

        Rules intent:
        - Multi-model unit: below starting strength if remaining model count < starting model count.
        - Starting Strength of 1 (single-model): below starting strength if the model has fewer wounds remaining
          than its starting wounds.

        Attached Leaders are treated as part of the unit for this check, consistent with other Battle-shock checks.

        Returns:
            bool: True if below starting strength.
        """
        # Attached Leaders are not evaluated separately; the Attached unit is treated as one unit.
        try:
            if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                return False
        except Exception:
            pass

        # Compute effective starting/current strength across attached members (bodyguard + leaders).
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [self]

        starting_models = 0
        current_models = 0
        starting_wounds = 0
        current_wounds = 0

        for u in members:
            try:
                starting_models += int(getattr(u, "starting_model_count", len(getattr(u, "models", []) or [])))
            except Exception:
                starting_models += 0
            try:
                current_models += int(len(getattr(u, "models", []) or []))
            except Exception:
                current_models += 0
            try:
                starting_wounds += int(getattr(u, "starting_total_wounds", 0) or 0)
            except Exception:
                pass
            try:
                for m in (getattr(u, "models", []) or []):
                    if getattr(m, "is_alive", True):
                        current_wounds += int(getattr(m, "wounds", 0) or 0)
            except Exception:
                pass

        # Multi-model unit: model-count based
        if starting_models > 1:
            return current_models < starting_models

        # Starting Strength of 1: wounds-based
        if starting_wounds <= 0:
            return False
        return current_wounds < starting_wounds

    def is_battle_shocked(self) -> bool:
        """
        Check if the unit is currently battle-shocked.
        
        Returns:
            bool: True if the unit has a BattleShockEffect status effect
        """
        return any(isinstance(effect, BattleShockEffect) for effect in list(getattr(self, "status_effects", []) or []))

    def clear_post_shoot_leadership_debuff(self) -> None:
        """Clear post-shoot Leadership/Battle-shock debuff effects from this unit."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "post_shoot_leadership_debuff_active",
            "post_shoot_leadership_debuff_owner",
            "post_shoot_leadership_debuff_turn",
            "post_shoot_leadership_debuff_value",
            "post_shoot_leadership_debuff_source",
        ):
            sr.pop(key, None)
        self.special_rules = sr

    def apply_wracked_with_agonies(
        self,
        *,
        owner_id: str,
        turn: int,
        source: str,
        move_penalty: int,
        charge_penalty: int,
    ) -> None:
        """Apply wracked-with-agonies penalties (Move -X, Charge -Y) until start of owner's next turn."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if sr.get("wracked_with_agonies_active"):
            self.clear_wracked_with_agonies()
            sr = getattr(self, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
        sr["wracked_with_agonies_active"] = True
        sr["wracked_with_agonies_owner"] = str(owner_id or "")
        sr["wracked_with_agonies_turn"] = int(turn or 0)
        sr["wracked_with_agonies_source"] = str(source or "Wracking Agonies").strip() or "Wracking Agonies"
        sr["wracked_with_agonies_move_penalty"] = int(move_penalty or 0)
        sr["wracked_with_agonies_charge_penalty"] = int(charge_penalty or 0)

        from ...utility.modifiers import Modifier, ModifierOp
        self.add_characteristic_modifier(
            "movement",
            Modifier(ModifierOp.ADD, int(move_penalty or 0), source="ability:wracked_with_agonies"),
        )

        mods = list(sr.get("charge_roll_modifiers", []) or [])
        mods.append(
            {
                "value": int(charge_penalty or 0),
                "source": sr["wracked_with_agonies_source"],
                "tag": "ability:wracked_with_agonies",
            }
        )
        sr["charge_roll_modifiers"] = mods
        self.special_rules = sr

    def clear_wracked_with_agonies(self) -> None:
        """Clear wracked-with-agonies penalties from this unit."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return
        self.remove_characteristic_modifiers_by_source("ability:wracked_with_agonies")
        mods = list(sr.get("charge_roll_modifiers", []) or [])
        kept = []
        for item in mods:
            if isinstance(item, dict) and item.get("tag") == "ability:wracked_with_agonies":
                continue
            kept.append(item)
        if kept:
            sr["charge_roll_modifiers"] = kept
        else:
            sr.pop("charge_roll_modifiers", None)
        for key in (
            "wracked_with_agonies_active",
            "wracked_with_agonies_owner",
            "wracked_with_agonies_turn",
            "wracked_with_agonies_source",
            "wracked_with_agonies_move_penalty",
            "wracked_with_agonies_charge_penalty",
            "wracked_with_agonies_source_unit_id",
            "wracked_with_agonies_source_model_id",
        ):
            sr.pop(key, None)
        self.special_rules = sr

    def apply_snared(
        self,
        *,
        owner_id: str,
        turn: int,
        source: str,
        weapon_key: str,
        weapon_name: str,
    ) -> None:
        """Apply snared effect to this unit until the start of the owner's next turn."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["snared_active"] = True
        sr["snared_owner"] = str(owner_id or "")
        sr["snared_turn"] = int(turn or 0)
        sr["snared_source"] = str(source or "Snared").strip() or "Snared"
        sr["snared_weapon_key"] = str(weapon_key or "").strip()
        sr["snared_weapon_name"] = str(weapon_name or "").strip()
        self.special_rules = sr

    def clear_snared(self) -> None:
        """Clear snared effect from this unit."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "snared_active",
            "snared_owner",
            "snared_turn",
            "snared_source",
            "snared_weapon_key",
            "snared_weapon_name",
        ):
            sr.pop(key, None)
        self.special_rules = sr

    def apply_pinned(
        self,
        *,
        owner_id: str,
        turn: int,
        source: str,
        move_penalty: int,
        charge_penalty: int,
        expires_phase: str = "COMMAND_PHASE",
    ) -> None:
        """Apply pinned penalties (Move -X, Charge -Y) until the configured owner phase start."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if sr.get("pinned_active"):
            self.clear_pinned()
        sr["pinned_active"] = True
        sr["pinned_owner"] = str(owner_id or "")
        sr["pinned_turn"] = int(turn or 0)
        sr["pinned_source"] = str(source or "Pinned").strip() or "Pinned"
        sr["pinned_move_penalty"] = int(move_penalty or 0)
        sr["pinned_charge_penalty"] = int(charge_penalty or 0)
        sr["pinned_expires_phase"] = str(expires_phase or "COMMAND_PHASE").strip().upper() or "COMMAND_PHASE"
        if hasattr(self, "add_characteristic_modifier"):
            from ...utility.modifiers import Modifier, ModifierOp
            self.add_characteristic_modifier(
                "movement",
                Modifier(ModifierOp.ADD, int(move_penalty or 0), source="ability:pinned"),
            )
        mods = list(sr.get("charge_roll_modifiers", []) or [])
        mods.append(
            {
                "value": int(charge_penalty or 0),
                "source": sr["pinned_source"],
                "tag": "ability:pinned",
            }
        )
        sr["charge_roll_modifiers"] = mods
        self.special_rules = sr

    def clear_pinned(self) -> None:
        """Clear pinned penalties from this unit."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return
        self.remove_characteristic_modifiers_by_source("ability:pinned")
        mods = list(sr.get("charge_roll_modifiers", []) or [])
        kept = []
        for item in mods:
            if isinstance(item, dict) and item.get("tag") == "ability:pinned":
                continue
            kept.append(item)
        if kept:
            sr["charge_roll_modifiers"] = kept
        else:
            sr.pop("charge_roll_modifiers", None)
        for key in (
            "pinned_active",
            "pinned_owner",
            "pinned_turn",
            "pinned_source",
            "pinned_move_penalty",
            "pinned_charge_penalty",
            "pinned_expires_phase",
        ):
            sr.pop(key, None)
        self.special_rules = sr

    def apply_aflame(
        self,
        *,
        owner_id: str,
        turn: int,
        source: str,
        move_penalty: int,
        advance_penalty: int,
        charge_penalty: int,
    ) -> None:
        """Apply aflame penalties (Move -X, Advance -Y, Charge -Z) until end of opponent's next turn."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if sr.get("aflame_active"):
            self.clear_aflame()
            sr = getattr(self, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
        sr["aflame_active"] = True
        sr["aflame_owner"] = str(owner_id or "")
        sr["aflame_turn"] = int(turn or 0)
        sr["aflame_source"] = str(source or "Aflame").strip() or "Aflame"
        sr["aflame_move_penalty"] = int(move_penalty or 0)
        sr["aflame_advance_penalty"] = int(advance_penalty or 0)
        sr["aflame_charge_penalty"] = int(charge_penalty or 0)

        from ...utility.modifiers import Modifier, ModifierOp
        self.add_characteristic_modifier(
            "movement",
            Modifier(ModifierOp.ADD, int(move_penalty or 0), source="ability:aflame"),
        )

        adv_mods = list(sr.get("advance_roll_modifiers", []) or [])
        adv_mods.append(
            {
                "value": int(advance_penalty or 0),
                "source": sr["aflame_source"],
                "tag": "ability:aflame",
            }
        )
        sr["advance_roll_modifiers"] = adv_mods

        charge_mods = list(sr.get("charge_roll_modifiers", []) or [])
        charge_mods.append(
            {
                "value": int(charge_penalty or 0),
                "source": sr["aflame_source"],
                "tag": "ability:aflame",
            }
        )
        sr["charge_roll_modifiers"] = charge_mods
        self.special_rules = sr

    def clear_aflame(self) -> None:
        """Clear aflame penalties from this unit."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return
        self.remove_characteristic_modifiers_by_source("ability:aflame")

        adv_mods = list(sr.get("advance_roll_modifiers", []) or [])
        kept_adv = []
        for item in adv_mods:
            if isinstance(item, dict) and item.get("tag") == "ability:aflame":
                continue
            kept_adv.append(item)
        if kept_adv:
            sr["advance_roll_modifiers"] = kept_adv
        else:
            sr.pop("advance_roll_modifiers", None)

        charge_mods = list(sr.get("charge_roll_modifiers", []) or [])
        kept_charge = []
        for item in charge_mods:
            if isinstance(item, dict) and item.get("tag") == "ability:aflame":
                continue
            kept_charge.append(item)
        if kept_charge:
            sr["charge_roll_modifiers"] = kept_charge
        else:
            sr.pop("charge_roll_modifiers", None)

        for key in (
            "aflame_active",
            "aflame_owner",
            "aflame_turn",
            "aflame_source",
            "aflame_move_penalty",
            "aflame_advance_penalty",
            "aflame_charge_penalty",
        ):
            sr.pop(key, None)
        self.special_rules = sr

    def apply_shocked(
        self,
        *,
        owner_id: str,
        turn: int,
        source: str,
        move_penalty: int,
        advance_penalty: int,
        charge_penalty: int,
    ) -> None:
        """Apply shocked penalties (Move -X, Advance -Y, Charge -Z) until end of opponent's next turn."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if sr.get("shocked_active"):
            self.clear_shocked()
            sr = getattr(self, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}

        sr["shocked_active"] = True
        sr["shocked_owner"] = str(owner_id or "")
        sr["shocked_turn"] = int(turn or 0)
        sr["shocked_source"] = str(source or "Shocked").strip() or "Shocked"
        sr["shocked_move_penalty"] = int(move_penalty or 0)
        sr["shocked_advance_penalty"] = int(advance_penalty or 0)
        sr["shocked_charge_penalty"] = int(charge_penalty or 0)

        from ...utility.modifiers import Modifier, ModifierOp
        self.add_characteristic_modifier(
            "movement",
            Modifier(ModifierOp.ADD, int(move_penalty or 0), source="ability:electro_shock"),
        )

        adv_mods = list(sr.get("advance_roll_modifiers", []) or [])
        adv_mods.append(
            {
                "value": int(advance_penalty or 0),
                "source": sr["shocked_source"],
                "tag": "ability:electro_shock",
            }
        )
        sr["advance_roll_modifiers"] = adv_mods

        charge_mods = list(sr.get("charge_roll_modifiers", []) or [])
        charge_mods.append(
            {
                "value": int(charge_penalty or 0),
                "source": sr["shocked_source"],
                "tag": "ability:electro_shock",
            }
        )
        sr["charge_roll_modifiers"] = charge_mods
        self.special_rules = sr

    def clear_shocked(self) -> None:
        """Clear shocked penalties from this unit."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return
        self.remove_characteristic_modifiers_by_source("ability:electro_shock")

        adv_mods = list(sr.get("advance_roll_modifiers", []) or [])
        kept_adv = []
        for item in adv_mods:
            if isinstance(item, dict) and item.get("tag") == "ability:electro_shock":
                continue
            kept_adv.append(item)
        if kept_adv:
            sr["advance_roll_modifiers"] = kept_adv
        else:
            sr.pop("advance_roll_modifiers", None)

        charge_mods = list(sr.get("charge_roll_modifiers", []) or [])
        kept_charge = []
        for item in charge_mods:
            if isinstance(item, dict) and item.get("tag") == "ability:electro_shock":
                continue
            kept_charge.append(item)
        if kept_charge:
            sr["charge_roll_modifiers"] = kept_charge
        else:
            sr.pop("charge_roll_modifiers", None)

        for key in (
            "shocked_active",
            "shocked_owner",
            "shocked_turn",
            "shocked_source",
            "shocked_move_penalty",
            "shocked_advance_penalty",
            "shocked_charge_penalty",
        ):
            sr.pop(key, None)
        self.special_rules = sr

    def apply_movement_phase_visible_wound_bonus(
        self,
        *,
        owner_id: str,
        turn: int,
        source: str,
        keyword: str,
        bonus: int,
        source_model_id: Optional[str] = None,
    ) -> None:
        """Apply a temporary +wound bonus vs this unit until the start of owner's next Command phase."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["movement_phase_visible_wound_bonus_active"] = True
        sr["movement_phase_visible_wound_bonus_owner"] = str(owner_id or "")
        sr["movement_phase_visible_wound_bonus_turn"] = int(turn or 0)
        sr["movement_phase_visible_wound_bonus_source"] = str(source or "Movement phase wound bonus").strip() or "Movement phase wound bonus"
        sr["movement_phase_visible_wound_bonus_keyword"] = str(keyword or "").strip()
        sr["movement_phase_visible_wound_bonus_value"] = int(bonus or 0)
        if source_model_id:
            sr["movement_phase_visible_wound_bonus_model_id"] = str(source_model_id)
        self.special_rules = sr

    def clear_movement_phase_visible_wound_bonus(self) -> None:
        """Clear temporary movement-phase wound bonus from this unit."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "movement_phase_visible_wound_bonus_active",
            "movement_phase_visible_wound_bonus_owner",
            "movement_phase_visible_wound_bonus_turn",
            "movement_phase_visible_wound_bonus_source",
            "movement_phase_visible_wound_bonus_keyword",
            "movement_phase_visible_wound_bonus_value",
            "movement_phase_visible_wound_bonus_model_id",
        ):
            sr.pop(key, None)
        self.special_rules = sr

    def apply_movement_phase_visible_hit_bonus(
        self,
        *,
        owner_id: str,
        turn: int,
        source: str,
        keyword: str,
        bonus: int,
        source_model_id: Optional[str] = None,
    ) -> None:
        """Apply a temporary +hit bonus vs this unit until the start of owner's next Command phase."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["movement_phase_visible_hit_bonus_active"] = True
        sr["movement_phase_visible_hit_bonus_owner"] = str(owner_id or "")
        sr["movement_phase_visible_hit_bonus_turn"] = int(turn or 0)
        sr["movement_phase_visible_hit_bonus_source"] = str(source or "Movement phase hit bonus").strip() or "Movement phase hit bonus"
        sr["movement_phase_visible_hit_bonus_keyword"] = str(keyword or "").strip()
        sr["movement_phase_visible_hit_bonus_value"] = int(bonus or 0)
        if source_model_id:
            sr["movement_phase_visible_hit_bonus_model_id"] = str(source_model_id)
        self.special_rules = sr

    def clear_movement_phase_visible_hit_bonus(self) -> None:
        """Clear temporary movement-phase hit bonus from this unit."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "movement_phase_visible_hit_bonus_active",
            "movement_phase_visible_hit_bonus_owner",
            "movement_phase_visible_hit_bonus_turn",
            "movement_phase_visible_hit_bonus_source",
            "movement_phase_visible_hit_bonus_keyword",
            "movement_phase_visible_hit_bonus_value",
            "movement_phase_visible_hit_bonus_model_id",
        ):
            sr.pop(key, None)
        self.special_rules = sr

    def get_movement_phase_visible_hit_bonus(self, attacker_unit=None, game=None) -> tuple[int, str]:
        """Return bonus/label if this unit is marked by a movement-phase hit bonus."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return 0, ""
        if not sr.get("movement_phase_visible_hit_bonus_active"):
            return 0, ""
        owner_id = str(sr.get("movement_phase_visible_hit_bonus_owner", "") or "")
        # Expire at the start of the owner's Command phase.
        if game is not None and owner_id:
            try:
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                phase_name = ""
            try:
                current_player = game.get_current_player()
                current_id = str(getattr(current_player, "id", "") or "")
            except Exception:
                current_id = ""
            if phase_name == "COMMAND_PHASE" and current_id == owner_id:
                self.clear_movement_phase_visible_hit_bonus()
                return 0, ""
        if attacker_unit is not None:
            try:
                army = attacker_unit.get_parent_army()
                player = getattr(army, "player", None)
            except Exception:
                player = None
            if owner_id and player is not None and str(getattr(player, "id", "") or "") != owner_id:
                return 0, ""
            keyword = str(sr.get("movement_phase_visible_hit_bonus_keyword", "") or "").strip()
            if keyword:
                try:
                    if not attacker_unit.has_any_keyword(keyword):
                        return 0, ""
                except Exception:
                    return 0, ""
        try:
            bonus = int(sr.get("movement_phase_visible_hit_bonus_value", 0) or 0)
        except Exception:
            bonus = 0
        if bonus <= 0:
            return 0, ""
        source = str(sr.get("movement_phase_visible_hit_bonus_source", "") or "Movement phase hit bonus").strip() or "Movement phase hit bonus"
        return int(bonus), f"+{int(bonus)} to hit from {source}"

    def get_movement_phase_visible_wound_bonus(self, attacker_unit=None, game=None) -> tuple[int, str]:
        """Return bonus/label if this unit is marked by a movement-phase wound bonus."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return 0, ""
        if not sr.get("movement_phase_visible_wound_bonus_active"):
            return 0, ""
        owner_id = str(sr.get("movement_phase_visible_wound_bonus_owner", "") or "")
        # Expire at the start of the owner's Command phase.
        if game is not None and owner_id:
            try:
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                phase_name = ""
            try:
                current_player = game.get_current_player()
                current_id = str(getattr(current_player, "id", "") or "")
            except Exception:
                current_id = ""
            if phase_name == "COMMAND_PHASE" and current_id == owner_id:
                self.clear_movement_phase_visible_wound_bonus()
                return 0, ""
        if attacker_unit is not None:
            try:
                army = attacker_unit.get_parent_army()
                player = getattr(army, "player", None)
            except Exception:
                player = None
            if owner_id and player is not None and str(getattr(player, "id", "") or "") != owner_id:
                return 0, ""
            keyword = str(sr.get("movement_phase_visible_wound_bonus_keyword", "") or "").strip()
            if keyword:
                try:
                    if not attacker_unit.has_any_keyword(keyword):
                        return 0, ""
                except Exception:
                    return 0, ""
        try:
            bonus = int(sr.get("movement_phase_visible_wound_bonus_value", 0) or 0)
        except Exception:
            bonus = 0
        if bonus <= 0:
            return 0, ""
        source = str(sr.get("movement_phase_visible_wound_bonus_source", "") or "Movement phase wound bonus").strip() or "Movement phase wound bonus"
        return int(bonus), f"+{int(bonus)} to wound from {source}"

    def apply_fight_phase_target_attack_bonus(
        self,
        *,
        owner_id: str,
        turn: int,
        source: str,
        keyword: str,
        attack_type: str,
        strength_bonus: int = 0,
        ap_bonus: int = 0,
        damage_bonus: int = 0,
        wound_bonus: int = 0,
        source_model_id: Optional[str] = None,
    ) -> None:
        """Apply a temporary fight-phase target bonus vs this unit."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        entries = list(sr.get("fight_phase_target_attack_bonuses", []) or [])
        atype = str(attack_type or "any").strip().lower()
        if atype not in ("melee", "ranged", "any"):
            atype = "any"
        entry = {
            "owner_id": str(owner_id or ""),
            "turn": int(turn or 0),
            "source": str(source or "Fight phase target bonus").strip() or "Fight phase target bonus",
            "keyword": str(keyword or "").strip(),
            "attack_type": atype,
            "strength_bonus": int(strength_bonus or 0),
            "ap_bonus": int(ap_bonus or 0),
            "damage_bonus": int(damage_bonus or 0),
            "wound_bonus": int(wound_bonus or 0),
        }
        if source_model_id:
            entry["source_model_id"] = str(source_model_id)
        entries.append(entry)
        sr["fight_phase_target_attack_bonuses"] = entries
        self.special_rules = sr

    def apply_fight_phase_melee_wound_penalty(
        self,
        *,
        owner_id: str,
        turn: int,
        source: str,
        penalty: int,
    ) -> None:
        """Apply a temporary fight-phase melee wound penalty to this unit's attacks."""
        try:
            penalty = int(penalty or 0)
        except Exception:
            penalty = 0
        if penalty <= 0:
            return
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        entries = list(sr.get("fight_phase_melee_wound_penalties", []) or [])
        entries.append(
            {
                "owner_id": str(owner_id or ""),
                "turn": int(turn or 0),
                "source": str(source or "Fight phase melee penalty").strip() or "Fight phase melee penalty",
                "penalty": int(penalty),
            }
        )
        sr["fight_phase_melee_wound_penalties"] = entries
        self.special_rules = sr

    def get_fight_phase_target_attack_bonuses(
        self,
        attacker_unit=None,
        *,
        game=None,
        attack_type: str = "any",
    ) -> dict:
        """Return aggregated fight-phase bonuses vs this unit for the attacker."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return {}
        entries = list(sr.get("fight_phase_target_attack_bonuses", []) or [])
        if not entries:
            return {}

        if game is None and attacker_unit is not None:
            try:
                army = attacker_unit.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None

        phase_name = ""
        current_turn = 0
        if game is not None:
            try:
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                phase_name = ""
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                current_turn = 0
        if phase_name and phase_name != "FIGHT_PHASE":
            # Expired outside fight phase.
            sr.pop("fight_phase_target_attack_bonuses", None)
            self.special_rules = sr
            return {}

        attacker_owner = ""
        if attacker_unit is not None:
            try:
                army = attacker_unit.get_parent_army()
                player = getattr(army, "player", None) if army is not None else None
                attacker_owner = str(get_entity_id(player) or getattr(player, "id", "") or "")
            except Exception:
                attacker_owner = ""

        atype = str(attack_type or "any").strip().lower()
        if atype not in ("melee", "ranged", "any"):
            atype = "any"

        active: list[dict] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if current_turn:
                try:
                    if int(entry.get("turn", 0) or 0) not in (0, current_turn):
                        continue
                except Exception:
                    pass
            if attacker_owner:
                owner_id = str(entry.get("owner_id", "") or "")
                if owner_id and owner_id != attacker_owner:
                    continue
            kw = str(entry.get("keyword", "") or "").strip()
            if kw and attacker_unit is not None:
                try:
                    if not self._unit_matches_keyword_phrase(attacker_unit, kw):
                        continue
                except Exception:
                    continue
            entry_attack_type = str(entry.get("attack_type", "") or "any").strip().lower()
            if entry_attack_type not in ("melee", "ranged", "any"):
                entry_attack_type = "any"
            if entry_attack_type != "any" and atype != "any" and entry_attack_type != atype:
                continue
            active.append(entry)

        if len(active) != len(entries):
            sr["fight_phase_target_attack_bonuses"] = active
            self.special_rules = sr

        if not active:
            return {}

        out = {
            "strength_bonus": 0,
            "ap_bonus": 0,
            "damage_bonus": 0,
            "wound_bonus": 0,
            "strength_reasons": [],
            "ap_reasons": [],
            "damage_reasons": [],
            "wound_reasons": [],
        }
        for entry in active:
            source = str(entry.get("source", "") or "Fight phase target bonus").strip() or "Fight phase target bonus"
            try:
                s_bonus = int(entry.get("strength_bonus", 0) or 0)
            except Exception:
                s_bonus = 0
            try:
                ap_bonus = int(entry.get("ap_bonus", 0) or 0)
            except Exception:
                ap_bonus = 0
            try:
                d_bonus = int(entry.get("damage_bonus", 0) or 0)
            except Exception:
                d_bonus = 0
            try:
                w_bonus = int(entry.get("wound_bonus", 0) or 0)
            except Exception:
                w_bonus = 0
            if s_bonus:
                out["strength_bonus"] += int(s_bonus)
                out["strength_reasons"].append(f"{source}: +{int(s_bonus)}S")
            if ap_bonus:
                out["ap_bonus"] += int(ap_bonus)
                out["ap_reasons"].append(f"{source}: +{int(ap_bonus)}AP")
            if d_bonus:
                out["damage_bonus"] += int(d_bonus)
                out["damage_reasons"].append(f"{source}: +{int(d_bonus)}D")
            if w_bonus:
                out["wound_bonus"] += int(w_bonus)
                out["wound_reasons"].append(f"{source}: +{int(w_bonus)} to wound")
        return out

    def apply_start_of_battle_keyword_reroll_choice(
        self,
        model: Optional['Model'],
        *,
        keyword: str,
        source: str = "",
        ability_key: Optional[str] = None,
    ) -> bool:
        """Persist a start-of-battle keyword reroll selection on the model."""
        if model is None:
            return False
        kw = str(keyword or "").strip().upper()
        if not kw:
            return False
        if not isinstance(getattr(model, "_temporary_effects", None), dict):
            model._temporary_effects = {}
        data = model._temporary_effects.get("start_of_battle_keyword_rerolls", {})
        if not isinstance(data, dict):
            data = {}
        key = str(ability_key or source or kw).strip().lower()
        if not key:
            key = kw.lower()
        data[key] = {
            "keyword": kw,
            "source": str(source or ""),
            "ability_key": key,
        }
        model._temporary_effects["start_of_battle_keyword_rerolls"] = data
        return True

    def get_start_of_battle_keyword_reroll_choice(
        self,
        model: Optional['Model'],
        *,
        ability_key: Optional[str] = None,
    ) -> Optional[dict]:
        """Return a stored keyword reroll selection for the model (if any)."""
        if model is None:
            return None
        eff = getattr(model, "_temporary_effects", {}) or {}
        data = eff.get("start_of_battle_keyword_rerolls", {})
        if not isinstance(data, dict):
            return None
        if ability_key is not None:
            key = str(ability_key or "").strip().lower()
            if key:
                return data.get(key)
        if len(data) == 1:
            try:
                return next(iter(data.values()))
            except Exception:
                return None
        return None

    def _iter_start_of_battle_keyword_reroll_choices(self, model: Optional['Model']) -> list[dict]:
        if model is None:
            return []
        eff = getattr(model, "_temporary_effects", {}) or {}
        data = eff.get("start_of_battle_keyword_rerolls", {})
        if isinstance(data, dict):
            return [v for v in data.values() if isinstance(v, dict)]
        if isinstance(data, list):
            return [v for v in data if isinstance(v, dict)]
        return []

    def _post_shoot_leadership_debuff_modifier(self, game=None) -> int:
        """Return persistent post-shoot Leadership/Battle-shock test modifier, clearing on expiry."""
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return 0
        if not sr.get("post_shoot_leadership_debuff_active"):
            return 0
        owner_id = str(sr.get("post_shoot_leadership_debuff_owner", "") or "")
        if game is not None and owner_id:
            try:
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                phase_name = ""
            try:
                current_player = game.get_current_player()
                current_id = str(getattr(current_player, "id", "") or "")
            except Exception:
                current_id = ""
            if phase_name == "SHOOTING_PHASE" and current_id == owner_id:
                self.clear_post_shoot_leadership_debuff()
                return 0
        try:
            return int(sr.get("post_shoot_leadership_debuff_value", 0) or 0)
        except Exception:
            return 0

    def _canticles_binharic_courage_test_modifier(self, game=None) -> int:
        """Return +1 when Binharic Courage (Mantra of Discipline) applies to this unit."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return 0
        try:
            if not bool(root.has_any_keyword("ADEPTUS MECHANICUS")):
                return 0
        except Exception:
            return 0

        if game is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return 0

        from ...rules.adeptus_mechanicus_canticles import (
            KEY_MANTRA_OF_DISCIPLINE,
            unit_has_active_canticles,
        )
        from ...utility.aura_utils import unit_within_range_of_unit
        from ...utility.entity_ids import get_entity_id

        seen_sources: set[str] = set()
        for source in list(game_map.get_friendly_units(root) or []):
            if source is None:
                continue
            try:
                source_root = source.get_attached_unit_root()
            except Exception:
                source_root = source
            if source_root is None:
                continue
            source_id = str(get_entity_id(source_root) or "")
            if source_id and source_id in seen_sources:
                continue
            if source_id:
                seen_sources.add(source_id)
            if not bool(unit_has_active_canticles(source_root, KEY_MANTRA_OF_DISCIPLINE)):
                continue
            try:
                if not bool(source_root.has_any_keyword("ADEPTUS MECHANICUS")):
                    continue
            except Exception:
                continue
            try:
                if bool(unit_within_range_of_unit(source_root, root, 6.0, use_attached_aggregate=True)):
                    return 1
            except Exception:
                continue
        return 0

    def pass_leadership_check(
        self,
        extra_reroll_sources: Optional[list[str]] = None,
        reroll_reason: str = "Leadership re-roll",
    ) -> bool:
        """Perform a Leadership test by rolling 2D6 against the unit's Leadership characteristic.
        
        Returns:
            bool: True if the test is passed, False if failed
        """
        roll_result = None
        dice_rolls = None
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "acts_of_faith", None) if army is not None else None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if mgr is not None and mgr.can_use_act_of_faith(self, game=game):
                roll_result, dice_rolls, _miracle_used = mgr.resolve_roll(
                    self,
                    roll_type="battle-shock",
                    game=game,
                    dice_count=2,
                    die_faces=6,
                )
        except Exception:
            roll_result = None
            dice_rolls = None
        if roll_result is None:
            roll_result = get_roll("2D6")
        leadership_value = self.leadership
        mod = 0
        try:
            army = self.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            mod = int(self._post_shoot_leadership_debuff_modifier(game))
            try:
                from ...utility.aura_effects import get_aura_battleshock_test_modifiers
                aura_mods = get_aura_battleshock_test_modifiers(self, game_map=getattr(game, "map", None))
                for val, _src in list(aura_mods or []):
                    mod += int(val)
            except Exception:
                pass
            mod += int(self._canticles_binharic_courage_test_modifier(game=game) or 0)
            try:
                dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
                modifier_fn = (
                    getattr(dg_mgr, "shamblerot_witherbone_pipes_leadership_test_modifier", None)
                    if dg_mgr is not None
                    else None
                )
                if callable(modifier_fn):
                    test_mod, _source = modifier_fn(self, game=game)
                    mod += int(test_mod or 0)
            except Exception:
                pass
            try:
                root_for_mod = self.get_attached_unit_root()
            except Exception:
                root_for_mod = self
            sr = getattr(root_for_mod, "special_rules", None)
            if isinstance(sr, dict):
                soulforged_mod = int(sr.get("soulforged_warpack_dark_pact_test_modifier", 0) or 0)
                mod += int(soulforged_mod)
        except Exception:
            mod = 0
        try:
            mod_roll = int(roll_result) + int(mod)
        except Exception:
            mod_roll = roll_result
        # 10e: lower Leadership is better; you pass if roll <= Ld.
        passed = mod_roll <= leadership_value
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            setattr(root, "_last_leadership_test_roll", int(roll_result))
        except Exception:
            setattr(root, "_last_leadership_test_roll", roll_result)
        try:
            setattr(root, "_last_leadership_test_modified_roll", int(mod_roll))
        except Exception:
            setattr(root, "_last_leadership_test_modified_roll", mod_roll)
        setattr(root, "_last_leadership_test_passed", bool(passed))

        reroll_sources = []
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            reroll_sources = list(root.leading_leadership_reroll_sources() or [])
        except Exception:
            reroll_sources = []
        try:
            checker = getattr(root, "_attached_unit_has_active_enhancement", None)
            has_proud = bool(
                callable(checker)
                and checker(
                    "enhancement_proud_and_vainglorious",
                    enhancement_id="000010018004",
                    enhancement_name="proud and vainglorious",
                )
            )
        except Exception:
            has_proud = False
        if has_proud:
            seen_proud = {str(src or "").strip().lower() for src in list(reroll_sources or []) if str(src or "").strip()}
            if "proud and vainglorious" not in seen_proud:
                reroll_sources.append("Proud and Vainglorious")
        try:
            army = root.get_parent_army() if root is not None else None
        except Exception:
            army = None
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        tempered_sources_fn = (
            getattr(sm_mgr, "wrath_of_the_rock_tempered_in_battle_reroll_sources", None)
            if sm_mgr is not None
            else None
        )
        if callable(tempered_sources_fn):
            try:
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            except Exception:
                game = None
            try:
                tempered_sources = list(tempered_sources_fn(root, game=game) or [])
            except Exception:
                tempered_sources = []
            if tempered_sources:
                seen_tempered = {str(src or "").strip().lower() for src in list(reroll_sources or []) if str(src or "").strip()}
                for src in tempered_sources:
                    label = str(src or "").strip()
                    if not label:
                        continue
                    key = label.lower()
                    if key in seen_tempered:
                        continue
                    seen_tempered.add(key)
                    reroll_sources.append(label)
        if extra_reroll_sources:
            seen = {str(src or "").strip().lower() for src in reroll_sources if str(src or "").strip()}
            for src in list(extra_reroll_sources or []):
                label = str(src or "").strip()
                if not label:
                    continue
                key = label.lower()
                if key in seen:
                    continue
                seen.add(key)
                reroll_sources.append(label)
        
        # Provide detailed feedback
        dice_note = ""
        try:
            if dice_rolls and isinstance(dice_rolls, list):
                dice_note = f" (dice {list(dice_rolls)})"
        except Exception:
            dice_note = ""
        if mod:
            if passed:
                logger.info(f"{self.name} Leadership test: 2D6 rolled {roll_result}{dice_note} (mod {mod:+}) "
                    f"-> {mod_roll} vs Ld {leadership_value} - PASSED! ")
            else:
                logger.error(f"{self.name} Leadership test: 2D6 rolled {roll_result}{dice_note} (mod {mod:+}) "
                    f"-> {mod_roll} vs Ld {leadership_value} - FAILED! ")
        else:
            if passed:
                logger.info(f"{self.name} Leadership test: 2D6 rolled {roll_result}{dice_note} vs Ld {leadership_value} - PASSED! ")
            else:
                logger.error(f"{self.name} Leadership test: 2D6 rolled {roll_result}{dice_note} vs Ld {leadership_value} - FAILED! ")

        if reroll_sources and not passed:
            want_reroll = True
            try:
                player = getattr(self.get_parent_army(), "player", None)
            except Exception:
                player = None
            try:
                game = getattr(player, "game", None) if player is not None else None
            except Exception:
                game = None
            try:
                game_map = getattr(game, "map", None) if game is not None else None
            except Exception:
                game_map = None
            try:
                provider = getattr(game_map, "roll_reroll_provider", None)
            except Exception:
                provider = None
            try:
                is_human = self._player_has_local_control(player)
            except Exception:
                is_human = False
            source_label = " / ".join(reroll_sources)
            if is_human and callable(provider):
                try:
                    want_reroll = bool(
                        provider(
                            player=player,
                            unit=self,
                            roll_type="leadership",
                            value=int(roll_result),
                            dice=dice_rolls,
                            needed=int(leadership_value),
                            success=passed,
                            reason=f"{source_label} ({reroll_reason})",
                            allow_reroll=True,
                        )
                    )
                except Exception:
                    want_reroll = False
            if want_reroll:
                original_roll = roll_result
                roll_result = get_roll("2D6")
                try:
                    mod_roll = int(roll_result) + int(mod)
                except Exception:
                    mod_roll = roll_result
                passed = mod_roll <= leadership_value
                try:
                    setattr(root, "_last_leadership_test_roll", int(roll_result))
                except Exception:
                    setattr(root, "_last_leadership_test_roll", roll_result)
                try:
                    setattr(root, "_last_leadership_test_modified_roll", int(mod_roll))
                except Exception:
                    setattr(root, "_last_leadership_test_modified_roll", mod_roll)
                setattr(root, "_last_leadership_test_passed", bool(passed))
                try:
                    from ...utility.event_bus import append_action
                    if player is not None:
                        append_action(
                            player,
                            f"{source_label}: {self.name} re-rolls Leadership test ({original_roll} -> {roll_result}).",
                        )
                except Exception:
                    pass
                if mod:
                    logger.info(f"{self.name} Leadership test re-roll: 2D6 rolled {roll_result} (mod {mod:+}) "
                        f"-> {mod_roll} vs Ld {leadership_value} - {'PASSED' if passed else 'FAILED'}")
                else:
                    logger.info(f"{self.name} Leadership test re-roll: 2D6 rolled {roll_result} "
                        f"-> {mod_roll} vs Ld {leadership_value} - {'PASSED' if passed else 'FAILED'}")
        
        return passed

    def pass_leadership_check_for_model(self, model: Optional['Model']) -> bool:
        """Perform a Leadership test for a specific model (2D6 vs that model's Leadership characteristic)."""
        if model is None:
            return False
        roll_result = None
        dice_rolls = None
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "acts_of_faith", None) if army is not None else None
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if mgr is not None and mgr.can_use_act_of_faith(self, game=game):
                roll_result, dice_rolls, _miracle_used = mgr.resolve_roll(
                    self,
                    roll_type="battle-shock",
                    game=game,
                    dice_count=2,
                    die_faces=6,
                )
        except Exception:
            roll_result = None
            dice_rolls = None
        if roll_result is None:
            roll_result = get_roll("2D6")
        try:
            leadership_value = int(getattr(model, "leadership", self.leadership))
        except Exception:
            leadership_value = self.leadership
        mod = 0
        try:
            army = self.get_parent_army()
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            mod = int(self._post_shoot_leadership_debuff_modifier(game))
            mod += int(self._canticles_binharic_courage_test_modifier(game=game) or 0)
            dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
            modifier_fn = (
                getattr(dg_mgr, "shamblerot_witherbone_pipes_leadership_test_modifier", None)
                if dg_mgr is not None
                else None
            )
            if callable(modifier_fn):
                test_mod, _source = modifier_fn(self, game=game)
                mod += int(test_mod or 0)
        except Exception:
            mod = 0
        try:
            mod_roll = int(roll_result) + int(mod)
        except Exception:
            mod_roll = roll_result
        passed = mod_roll <= leadership_value

        dice_note = ""
        try:
            if dice_rolls and isinstance(dice_rolls, list):
                dice_note = f" (dice {list(dice_rolls)})"
        except Exception:
            dice_note = ""
        model_name = getattr(model, "name", "Model")
        if mod:
            if passed:
                logger.info(f"{model_name} Leadership test: 2D6 rolled {roll_result}{dice_note} (mod {mod:+}) "
                    f"-> {mod_roll} vs Ld {leadership_value} - PASSED! ")
            else:
                logger.error(f"{model_name} Leadership test: 2D6 rolled {roll_result}{dice_note} (mod {mod:+}) "
                    f"-> {mod_roll} vs Ld {leadership_value} - FAILED! ")
        else:
            if passed:
                logger.info(f"{model_name} Leadership test: 2D6 rolled {roll_result}{dice_note} vs Ld {leadership_value} - PASSED! ")
            else:
                logger.error(f"{model_name} Leadership test: 2D6 rolled {roll_result}{dice_note} vs Ld {leadership_value} - FAILED! ")

        return passed

    @property
    def is_epic_hero(self) -> bool:
        return "Epic Hero" in self.keywords

    @property
    def is_battleline(self) -> bool:
        return "Battleline" in self.keywords

    @property
    def is_dedicated_transport(self) -> bool:
        return self.has_keyword("Dedicated Transport")

    @property
    def is_transport(self) -> bool:
        return self.has_keyword("Transport")

    @property
    def is_embarked(self) -> bool:
        return self.embarked_in is not None

    def cannot_embark(self) -> bool:
        """Return True if this unit is forbidden from embarking in a Transport."""
        try:
            if self.has_support_artillery_ability():
                return True
        except Exception:
            pass
        try:
            supports = list(getattr(self, "attached_support_units", []) or [])
            if supports:
                for support in supports:
                    if support is None:
                        continue
                    allows_embark = False
                    allows_embark_fn = getattr(support, "joined_support_allows_embark_while_joined", None)
                    if callable(allows_embark_fn):
                        allows_embark = bool(allows_embark_fn())
                    if not allows_embark:
                        return True
        except Exception:
            pass
        try:
            if getattr(self, "support_joined_to", None) is not None:
                allows_embark_fn = getattr(self, "joined_support_allows_embark_while_joined", None)
                allows_embark = bool(allows_embark_fn()) if callable(allows_embark_fn) else False
                if not allows_embark:
                    return True
        except Exception:
            pass
        return False

    def _parse_transport_capacity(self, datasheet) -> int:
        """
        Best-effort parsing for 10th edition Transport Capacity.

        Wahapedia data typically stores this as an ability entry on the datasheet (often "Transport"),
        with descriptions like "Transport Capacity: 12" or "Transport 12".
        """
        # Prefer the explicit `datasheet.transport` field (Wahapedia)
        try:
            t = str(getattr(datasheet, "transport", "") or "").strip()
            if t:
                m = re.search(r"transport\s+capacity\s+(?:of\s+)?(\d+)", t, flags=re.IGNORECASE)
                if m:
                    return int(m.group(1))
                m = re.search(r"transport\s*capacity\s*[:\-]\s*(\d+)", t, flags=re.IGNORECASE)
                if m:
                    return int(m.group(1))
        except Exception:
            pass

        try:
            keywords = getattr(datasheet, "keywords", []) or []
            if "Transport" not in keywords and "Dedicated Transport" not in keywords:
                return 0
        except Exception:
            # If keywords can't be read, fall back to parsing abilities only.
            pass

        candidates: List[str] = []
        try:
            if hasattr(datasheet, 'datasheets_abilities'):
                for a in datasheet.datasheets_abilities:
                    # Prefer raw description/name if present
                    n = str(a.get("name", "") or "")
                    d = str(a.get("description", "") or "")
                    if d:
                        candidates.append(f"{n} {d}".strip())
                    elif n:
                        candidates.append(n.strip())
        except Exception:
            candidates = []

        text = " \n ".join([c for c in candidates if c])
        if not text:
            return 0

        # Common patterns across sources
        patterns = [
            r"transport\s*capacity\s*[:\-]\s*(\d+)",
            r"\btransport\s*\(?\s*(\d+)\s*\)?\b",
        ]
        for pat in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    continue
        return 0

    def _parse_transport_restrictions(self, datasheet) -> Tuple[set[str], set[str]]:
        """
        Parse best-effort keyword restrictions from the datasheet's `transport` text.

        Example:
        "This model has a transport capacity of 12 HERETIC ASTARTES INFANTRY models.
         It cannot transport TERMINATOR, JUMP PACK, OBLITERATOR or POSSESSED models."
        """
        required: set[str] = set()
        excluded: set[str] = set()

        try:
            text = str(getattr(datasheet, "transport", "") or "")
        except Exception:
            text = ""
        if not text:
            return required, excluded

        # Required clause between capacity number and "models"
        m = re.search(r"transport\s+capacity\s+(?:of\s+)?\d+\s+(.+?)\s+models?\b", text, flags=re.IGNORECASE)
        req_clause = (m.group(1) or "").strip() if m else ""
        if req_clause:
            known: List[str] = []
            try:
                known.extend(list(getattr(datasheet, "keywords", []) or []))
            except Exception:
                pass
            try:
                known.extend(list(getattr(datasheet, "faction_keywords", []) or []))
            except Exception:
                pass
            # Common keywords seen in transport restrictions
            known.extend(["Infantry", "Beast", "Mounted", "Jump Pack", "Terminator", "Possessed", "Obliterator", "Gravis", "Phobos"])

            upper_clause = req_clause.upper()
            for kw in known:
                try:
                    if re.search(rf"(?<![A-Z0-9]){re.escape(str(kw).upper())}(?![A-Z0-9])", upper_clause):
                        required.add(str(kw))
                except Exception:
                    continue

        # Excluded clause: "cannot transport ..."
        m2 = re.search(r"cannot\s+transport\s+(.+?)(?:\.\s*|$)", text, flags=re.IGNORECASE)
        excl_clause = (m2.group(1) or "").strip() if m2 else ""
        if excl_clause:
            excl_clause = re.sub(r"\bmodels?\b", "", excl_clause, flags=re.IGNORECASE).strip()
            parts = re.split(r"\s*,\s*|\s+or\s+|\s+and\s+", excl_clause, flags=re.IGNORECASE)
            for p in parts:
                token = (p or "").strip()
                if not token:
                    continue
                excluded.add(token.title() if token.isupper() else token)

        return required, excluded

    def get_transport_slots_required(self) -> int:
        """How many transport 'slots' this unit uses. Default: 1 per alive model."""
        # Datasheets can have non-1 model slot costs (e.g. Terminators, Jump Packs), but we don't
        # have a unified schema for that yet. Keep this conservative and overridable.
        # Attached leader units should never be embarked separately; count them via the bodyguard.
        try:
            if bool(getattr(self, "is_attached_leader", False)):
                return 0
        except Exception:
            pass
        # Imperial Agents Kill Team: specific models count as 2 slots.
        has_kill_team = False
        try:
            root = self.get_attached_unit_root()
            if root is not None and hasattr(root, "attached_unit_has_kill_team"):
                has_kill_team = bool(root.attached_unit_has_kill_team())
        except Exception:
            has_kill_team = False
        try:
            # If this unit has attached leaders, include their models for capacity.
            try:
                models = self.get_models_for_collision()
            except Exception:
                models = self.models
            total = 0
            for m in (models or []):
                try:
                    if not getattr(m, "is_alive", False):
                        continue
                except Exception:
                    continue
                slot_cost = int(self.get_transport_slot_cost_for_model(m) or 1)
                if has_kill_team and self._kill_team_model_uses_two_transport_slots(m):
                    slot_cost = max(slot_cost, 2)
                total += max(1, slot_cost)
            return int(total)
        except Exception:
            return len(self.models)

    def _embarking_slot_rule(self) -> str:
        """
        Return EMBARKING slot rule variant for this attached-unit root.

        Supported variants:
        - ``all_models``: each model counts as 2 slots while embarked.
        - ``heavy_weapons_gunner``: Heavy Weapons Gunner models count as 2 slots while embarked.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        cache_key = "embarking_slot_rule"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return str(cache.get(cache_key) or "")

        rule = ""
        iter_texts = getattr(root, "_iter_active_ability_texts", None)
        normalize = getattr(root, "_normalize_rules_text", None)
        if callable(iter_texts):
            for raw_text in iter_texts():
                text = str(raw_text or "")
                if not text:
                    continue
                if callable(normalize):
                    text = normalize(text)
                low = text.lower().replace("\u2019", "'")
                if "while embarked within a transport" not in low:
                    continue
                if "for the purposes of the firing deck ability" not in low:
                    continue
                if (
                    "each model takes up the space of 2 models" in low
                    and "each weapon equipped by these models is considered to be 2 models" in low
                ):
                    rule = "all_models"
                    break
                if (
                    "each heavy weapons gunner model takes up the space of 2 models" in low
                    and "each weapon equipped by these models is considered to be 2 models" in low
                ):
                    rule = "heavy_weapons_gunner"
                    break

        if not isinstance(cache, dict):
            try:
                root._ability_cache = {}
                cache = root._ability_cache
            except Exception:
                cache = None
        if isinstance(cache, dict):
            cache[cache_key] = str(rule or "")
        return str(rule or "")

    def _is_heavy_weapons_gunner_model(self, model: Optional[Model]) -> bool:
        if model is None:
            return False
        name = _normalize_unit_name_for_rules(getattr(model, "name", "") or "")
        return "heavy weapons gunner" in name

    def _model_transport_embark_slot_override(self) -> int:
        """Return model-specific embark slot override from active ability text."""
        cache_key = "model_transport_embark_slot_override"
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return int(cache.get(cache_key) or 0)

        slot_override = 0
        iter_texts = getattr(self, "_iter_active_ability_texts", None)
        normalize = getattr(self, "_normalize_rules_text", None)
        if callable(iter_texts):
            for raw_text in iter_texts():
                text = str(raw_text or "")
                if not text:
                    continue
                if callable(normalize):
                    text = normalize(text)
                normalized = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
                normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized).strip()
                if not normalized:
                    continue
                match = _MODEL_EMBARKING_WITHIN_TRANSPORTS_RE.fullmatch(normalized)
                if not match:
                    continue
                slot_override = max(slot_override, int(match.group("slots") or 0))

        if not isinstance(cache, dict):
            cache = {}
            self._ability_cache = cache
        cache[cache_key] = int(slot_override)
        return int(slot_override)

    def get_transport_slot_cost_for_model(self, model: Optional[Model]) -> int:
        """Return per-model embark slot cost for this unit (default 1)."""
        if model is None:
            return 1
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is not self:
            return int(root.get_transport_slot_cost_for_model(model) or 1)

        # LOYAL PROTECTOR joined-support model uses 3 slots while joined to a Command Squad.
        source_unit = getattr(model, "parent_unit", None)
        if source_unit is None:
            for support in list(getattr(self, "attached_support_units", []) or []):
                if support is None:
                    continue
                if model in list(getattr(support, "models", []) or []):
                    source_unit = support
                    break
        if source_unit is not None and source_unit is not self:
            if getattr(source_unit, "support_joined_to", None) is self:
                kind_fn = getattr(source_unit, "_joined_support_rule_kind", None)
                kind = str(kind_fn() or "").strip().lower() if callable(kind_fn) else ""
                if kind == "loyal_protector":
                    return 3

        model_unit = source_unit if source_unit is not None else self
        slot_override_fn = getattr(model_unit, "_model_transport_embark_slot_override", None)
        if callable(slot_override_fn):
            slot_override = int(slot_override_fn() or 0)
            if slot_override > 0:
                return slot_override

        rule = self._embarking_slot_rule()
        if rule == "all_models":
            return 2
        if rule == "heavy_weapons_gunner" and self._is_heavy_weapons_gunner_model(model):
            return 2
        return 1

    def get_firing_deck_weapon_slots_for_model(self, model: Optional[Model]) -> int:
        """
        Return how many Firing Deck 'model weapons' this model consumes.

        For EMBARKING variants, this matches transport slot weighting.
        """
        return int(self.get_transport_slot_cost_for_model(model) or 1)

    def get_firing_deck_selection_cost(self, model: Optional[Model]) -> int:
        """Resolve Firing Deck selection cost for an embarked model from its parent unit context."""
        if model is None:
            return 1
        source_unit = getattr(model, "parent_unit", None)
        if source_unit is None:
            return 1
        try:
            source_root = source_unit.get_attached_unit_root()
        except Exception:
            source_root = source_unit
        getter = getattr(source_root, "get_firing_deck_weapon_slots_for_model", None)
        if not callable(getter):
            return 1
        try:
            return max(1, int(getter(model) or 1))
        except Exception:
            return 1

    def _kill_team_model_uses_two_transport_slots(self, model: Model) -> bool:
        name = str(getattr(model, "name", "") or "").lower()
        if not name:
            return False
        tokens = ("terminator", "outrider", "biker", "jump pack", "jump-pack")
        return any(tok in name for tok in tokens)

    @property
    def transport_slots_used(self) -> int:
        try:
            return sum(u.get_transport_slots_required() for u in (self.transport_passengers or []) if u and u.is_alive())
        except Exception:
            return 0

    @property
    def transport_slots_remaining(self) -> int:
        return max(0, int(self.transport_capacity or 0) - int(self.transport_slots_used or 0))

    def _transport_keyword_check_members(self) -> list["Unit"]:
        root = self.get_attached_unit_root()
        members: list["Unit"] = [root]
        for support in list(getattr(root, "attached_support_units", []) or []):
            if support is not None:
                members.append(support)
        for leader in list(getattr(root, "attached_leaders", []) or []):
            if leader is not None:
                members.append(leader)

        ordered: list["Unit"] = []
        seen: set[int] = set()
        for member in members:
            key = id(member)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(member)
        return ordered

    @staticmethod
    def _transport_member_has_local_keyword(member: "Unit", keyword: str) -> bool:
        if member is None:
            return False
        has_local = getattr(member, "has_any_keyword_local", None)
        if callable(has_local):
            return bool(has_local(keyword))
        has_any = getattr(member, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any(keyword))
        return False

    def _attached_leaders_with_bodyguard_transport_embark_override(self) -> set[str]:
        root = self.get_attached_unit_root()
        if root is not self:
            return root._attached_leaders_with_bodyguard_transport_embark_override()

        cache_key = "bodyguard_transport_embark_override_leader_ids"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return set(str(v) for v in list(cache.get(cache_key) or []))

        matched_ids: set[str] = set()
        for ability, leader in root._iter_attached_leader_leading_abilities():
            if isinstance(ability, str):
                name = str(ability or "")
                desc = str(ability or "")
            else:
                name = str(getattr(ability, "name", "") or "")
                desc = str(getattr(ability, "description", "") or "") or name
            text_src = leader._strip_eligibility_prefix(desc or name or "")
            normalized = str(leader._normalize_rules_text(text_src) or "")
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not normalized:
                continue
            if _BODYGUARD_TRANSPORT_EMBARK_OVERRIDE_RE.search(normalized) is None:
                continue
            leader_id = str(get_entity_id(leader) or "").strip()
            if leader_id:
                matched_ids.add(leader_id)
            else:
                matched_ids.add(f"obj:{id(leader)}")

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = sorted(matched_ids)
        root._ability_cache = cache
        return set(matched_ids)

    def _transport_member_inherits_bodyguard_embark_eligibility(self, member: "Unit") -> bool:
        root = self.get_attached_unit_root()
        if member is None or member is root:
            return False

        if getattr(member, "support_joined_to", None) is root:
            allows_embark = getattr(member, "joined_support_allows_embark_while_joined", None)
            if callable(allows_embark) and bool(allows_embark()):
                return True

        if not bool(getattr(member, "is_attached_leader", False)):
            return False

        override_ids = root._attached_leaders_with_bodyguard_transport_embark_override()
        member_id = str(get_entity_id(member) or "").strip()
        if member_id and member_id in override_ids:
            return True
        return f"obj:{id(member)}" in override_ids

    def can_transport(self, passenger_unit: 'Unit') -> bool:
        """Core eligibility + capacity check (datasheet-specific restrictions are best-effort)."""
        if passenger_unit is None:
            return False
        get_root = getattr(passenger_unit, "get_attached_unit_root", None)
        if callable(get_root):
            passenger_root = get_root()
            if passenger_root is not None:
                passenger_unit = passenger_root
        if passenger_unit == self:
            return False
        if not self.is_transport:
            return False
        if not self.is_alive():
            return False
        sr_transport = getattr(self, "special_rules", None)
        if isinstance(sr_transport, dict) and bool(sr_transport.get("drop_pod_embark_locked", False)):
            return False
        if passenger_unit.is_embarked:
            return False
        try:
            if callable(getattr(passenger_unit, "cannot_embark", None)) and passenger_unit.cannot_embark():
                return False
        except Exception:
            pass
        # Must be a friendly unit
        try:
            if self.get_parent_army() is None or passenger_unit.get_parent_army() is None:
                return False
            if self.get_parent_army() != passenger_unit.get_parent_army():
                return False
        except Exception:
            return False
        army = self.get_parent_army()
        csm_mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        match_fn = getattr(csm_mgr, "pactbound_zealots_transport_marks_match", None) if csm_mgr is not None else None
        if callable(match_fn) and not bool(match_fn(self, passenger_unit)):
            return False
        # Datasheet-specific restrictions (from Wahapedia `datasheet.transport` field when present)
        req = getattr(self, "transport_required_keywords", set()) or set()
        excl = getattr(self, "transport_excluded_keywords", set()) or set()
        keyword_members = passenger_unit._transport_keyword_check_members()
        if req:
            for member in keyword_members:
                if passenger_unit._transport_member_inherits_bodyguard_embark_eligibility(member):
                    continue
                for kw in req:
                    if not passenger_unit._transport_member_has_local_keyword(member, str(kw)):
                        return False
        else:
            # Default core restriction: transports carry Infantry (unless specified otherwise).
            for member in keyword_members:
                if passenger_unit._transport_member_inherits_bodyguard_embark_eligibility(member):
                    continue
                if not passenger_unit._transport_member_has_local_keyword(member, "Infantry"):
                    return False
        if excl:
            for member in keyword_members:
                if passenger_unit._transport_member_inherits_bodyguard_embark_eligibility(member):
                    continue
                for kw in excl:
                    if passenger_unit._transport_member_has_local_keyword(member, str(kw)):
                        return False
        # Capacity
        needed = passenger_unit.get_transport_slots_required()
        if needed <= 0:
            return False
        if self.transport_capacity <= 0:
            return False
        return (self.transport_slots_used + needed) <= self.transport_capacity

    def add_passenger(self, passenger_unit: 'Unit', game_map: 'Map') -> bool:
        """Embark bookkeeping. Removes passenger from the map."""
        if game_map is None:
            raise RuntimeError("Embark requires an active game map.")
        if not self.can_transport(passenger_unit):
            return False
        if passenger_unit in self.transport_passengers:
            return True
        self.transport_passengers.append(passenger_unit)
        passenger_unit.embarked_in = self
        passenger_unit.round_state.embarked_this_round = True
        # If passenger is an attached-unit root, mark attached leaders as embarked too.
        for leader in list(getattr(passenger_unit, "attached_leaders", []) or []):
            if leader is None:
                continue
            leader.embarked_in = self
            leader.round_state.embarked_this_round = True
            if leader in game_map.units:
                game_map.units.remove(leader)
            leader.position = None
            publish_fn = getattr(leader, "_publish_unit_event", None)
            if callable(publish_fn):
                publish_fn("unit_embarked", unit=leader, transport_unit=self)
                publish_fn("unit_state_changed", unit=leader, reason="embarked", transport_unit=self)
        # Remove from battlefield representation
        if passenger_unit in game_map.units:
            game_map.units.remove(passenger_unit)
        # Clear a concrete battlefield position while embarked
        passenger_unit.position = None
        passenger_unit._publish_unit_event("unit_embarked", unit=passenger_unit, transport_unit=self)
        passenger_unit._publish_unit_event("unit_state_changed", unit=passenger_unit, reason="embarked", transport_unit=self)
        return True

    def remove_passenger(self, passenger_unit: 'Unit') -> None:
        if passenger_unit in self.transport_passengers:
            self.transport_passengers.remove(passenger_unit)
        if getattr(passenger_unit, "embarked_in", None) == self:
            passenger_unit.embarked_in = None
        # Clear embarked state for attached leaders as well.
        for leader in list(getattr(passenger_unit, "attached_leaders", []) or []):
            if leader is None:
                continue
            if getattr(leader, "embarked_in", None) == self:
                leader.embarked_in = None
            publish_fn = getattr(leader, "_publish_unit_event", None)
            if callable(publish_fn):
                publish_fn("unit_disembarked", unit=leader, transport_unit=self)
                publish_fn("unit_state_changed", unit=leader, reason="disembarked", transport_unit=self)
        passenger_unit._publish_unit_event("unit_disembarked", unit=passenger_unit, transport_unit=self)
        passenger_unit._publish_unit_event("unit_state_changed", unit=passenger_unit, reason="disembarked", transport_unit=self)
        transport_sr = getattr(self, "special_rules", None)
        if isinstance(transport_sr, dict) and bool(transport_sr.get("drop_pod_embark_lock_pending", False)):
            if not list(getattr(self, "transport_passengers", []) or []):
                transport_sr["drop_pod_embark_locked"] = True
                transport_sr["drop_pod_embark_lock_pending"] = False
                if "drop_pod_embark_lock_source" not in transport_sr:
                    source = str(transport_sr.get("drop_pod_assault_source", "") or "").strip()
                    if source:
                        transport_sr["drop_pod_embark_lock_source"] = source
                self.special_rules = transport_sr

    @property
    def is_leader(self) -> bool:
        try:
            return len(self.can_be_attached_to) > 0
        except Exception:
            return False

    @property
    def is_attached_leader(self) -> bool:
        """True if this Leader is currently attached to a Bodyguard unit."""
        return bool(self.is_leader and getattr(self, "attached_to", None) is not None)

    @property
    def is_support_artillery_joined(self) -> bool:
        """True if this Support Artillery model is joined to a unit."""
        return bool(getattr(self, "support_joined_to", None) is not None)

    @property
    def is_joined_support(self) -> bool:
        """Alias for support artillery joined status (used for UI filtering)."""
        return self.is_support_artillery_joined

    def get_attachment_target(self):
        """Return the unit this model is attached/joined to, if any."""
        if self.is_leader:
            return getattr(self, "attached_to", None)
        if self.has_joined_support_ability():
            return getattr(self, "support_joined_to", None)
        return None

    def joined_support_allows_embark_while_joined(self) -> bool:
        if getattr(self, "support_joined_to", None) is None:
            return False
        return str(self._joined_support_rule_kind() or "").strip().lower() == "loyal_protector"

    def get_datasheet_id(self) -> Optional[str]:
        try:
            return getattr(self._datasheet, "id", None)
        except Exception:
            return None

    def get_attached_unit_root(self) -> 'Unit':
        """Return the 'root' unit for this attached unit group (Bodyguard if attached, else self)."""
        if self.is_leader and getattr(self, "attached_to", None) is not None:
            return self.attached_to
        if getattr(self, "support_joined_to", None) is not None:
            return self.support_joined_to
        return self

    def get_attached_unit_members(self) -> List['Unit']:
        """Return all Unit objects that move/deploy/embark together as one Attached unit."""
        root = self.get_attached_unit_root()
        try:
            leaders = list(getattr(root, "attached_leaders", []) or [])
        except Exception:
            leaders = []
        try:
            supports = list(getattr(root, "attached_support_units", []) or [])
        except Exception:
            supports = []
        # Root first, then leaders
        return [root] + [u for u in supports if u is not None] + [u for u in leaders if u is not None]

    def get_attached_unit_models(self) -> List['Model']:
        """Flatten models across the attached unit members (bodyguard + leaders)."""
        models: List['Model'] = []
        for u in self.get_attached_unit_members():
            try:
                for m in list(getattr(u, "models", []) or []):
                    if getattr(m, "_pending_placement", False):
                        continue
                    models.append(m)
            except Exception:
                continue
        return models

    def _get_bodyguard_support_models(self) -> List['Model']:
        """Return bodyguard models plus any joined support-artillery models (root only)."""
        root = self.get_attached_unit_root()
        if root is not self:
            try:
                return root._get_bodyguard_support_models()
            except Exception:
                return list(getattr(root, "models", []) or [])
        models: List['Model'] = []
        try:
            models.extend(list(getattr(root, "models", []) or []))
        except Exception:
            pass
        try:
            for su in list(getattr(root, "attached_support_units", []) or []):
                models.extend(list(getattr(su, "models", []) or []))
        except Exception:
            pass
        return models

    def get_kill_team_majority_toughness(self) -> Optional[int]:
        """
        Return the majority Toughness across models in this attached unit.
        If tied, return the highest Toughness.
        """
        try:
            models = list(self.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(self, "models", []) or [])
        if not models:
            return None
        counts: dict[int, int] = {}
        for m in models:
            try:
                if not getattr(m, "is_alive", False):
                    continue
            except Exception:
                pass
            try:
                t_val = int(getattr(m, "toughness", getattr(m, "_toughness", 0)) or 0)
            except Exception:
                continue
            if t_val <= 0:
                continue
            counts[t_val] = counts.get(t_val, 0) + 1
        if not counts:
            return None
        max_count = max(counts.values())
        tied = [t for (t, c) in counts.items() if c == max_count]
        return max(tied) if tied else None

    def get_models_for_rendering(self) -> List['Model']:
        """Models used for battlefield rendering/hover detection (include attached Leaders)."""
        root = self.get_attached_unit_root()
        # If called on a Leader that's attached, render is handled by the bodyguard root.
        if root is not self:
            try:
                return root.get_models_for_rendering()
            except Exception:
                return list(getattr(root, "models", []) or [])
        return self.get_attached_unit_models()

    def get_models_for_collision(self) -> List['Model']:
        """Models used for collision/pathfinding/LOS checks (include attached Leaders)."""
        root = self.get_attached_unit_root()
        if root is not self:
            try:
                return root.get_models_for_collision()
            except Exception:
                return list(getattr(root, "models", []) or [])
        return self.get_attached_unit_models()

    def is_within_objective_range(self, objective_point) -> bool:
        """Return True if any alive model in this unit is within objective control range."""
        if objective_point is None:
            return False
        try:
            if not self.is_alive() or not getattr(self, "deployed", False):
                return False
        except Exception:
            return False
        try:
            if bool(getattr(self, "is_embarked", False)) or self.is_in_reserves():
                return False
        except Exception:
            pass
        try:
            models = list(self.get_models_for_collision() or [])
        except Exception:
            models = list(getattr(self, "models", []) or [])
        models = [m for m in models if bool(getattr(m, "is_alive", True))]
        if not models:
            return False
        try:
            from shapely.geometry import Point as _ShPoint
            area = _ShPoint(objective_point.x, objective_point.y).buffer(
                float(getattr(objective_point, "control_radius", 0.0) or 0.0)
            )
        except Exception:
            area = None
        for model in models:
            try:
                if area is not None:
                    base = model.model_base.get_base_shape()
                    if base.intersects(area):
                        return True
            except Exception:
                pass
            try:
                pos = model.get_location()
            except Exception:
                pos = None
            if not pos:
                continue
            try:
                dx = float(pos[0]) - float(getattr(objective_point, "x", 0.0))
                dy = float(pos[1]) - float(getattr(objective_point, "y", 0.0))
                radius = float(getattr(objective_point, "control_radius", 0.0) or 0.0)
                base_r = float(getattr(model.model_base, "get_radius", lambda: 1.0)())
                if (dx * dx + dy * dy) ** 0.5 <= (radius + base_r):
                    return True
            except Exception:
                continue
        return False

    def get_models_for_wound_allocation(self) -> List['Model']:
        """
        Models eligible to be allocated wounds for this unit right now.

        For Attached units:
        - While any bodyguard models remain, allocate to bodyguards only.
        - Once bodyguards are gone (but separation is pending until the end of an attack sequence),
          allocate to the attached leaders' models.
        """
        # If this is an attached Leader, allocation is handled by the bodyguard unit.
        try:
            if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                return []
        except Exception:
            pass
        # If this is a joined Support Artillery model, allocation is handled by the bodyguard unit.
        try:
            if bool(getattr(self, "is_support_artillery_joined", False)):
                return []
        except Exception:
            pass

        # Bodyguard models first
        try:
            bodyguards = list(self._get_bodyguard_support_models() or [])
        except Exception:
            bodyguards = list(getattr(self, "models", []) or [])
        bodyguards_alive = [
            m for m in bodyguards
            if getattr(m, "is_alive", True) and not getattr(m, "_pending_placement", False)
        ]
        if bodyguards_alive:
            return bodyguards_alive

        # If no bodyguards remain, allocate to leader models (if any)
        leaders_models: list['Model'] = []
        try:
            for l in list(getattr(self, "attached_leaders", []) or []):
                for m in (getattr(l, "models", []) or []):
                    if getattr(m, "is_alive", True) and not getattr(m, "_pending_placement", False):
                        leaders_models.append(m)
        except Exception:
            pass
        return leaders_models

    def get_effective_keywords(self) -> List[str]:
        """Effective keywords for rules checks while attached (union of all members and all models)."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [self]
        kws: list[str] = []
        seen: set[str] = set()
        for u in members:
            try:
                hover_active = bool(getattr(u, "hover_mode", False))
                smoke_suppressed = False
                removed_keywords: set[str] = set()
                sr = getattr(u, "special_rules", None)
                if isinstance(sr, dict):
                    for k in list(sr.get("ability_removed_keywords", []) or []):
                        key = str(k or "").strip().lower()
                        if key:
                            removed_keywords.add(key)
                try:
                    fell_back = bool(getattr(getattr(u, "round_state", None), "fell_back_this_round", False))
                    loses_smoke = bool(getattr(u, "loses_smoke_keyword_when_shooting_after_fall_back", lambda: False)())
                    smoke_suppressed = fell_back and loses_smoke
                except Exception:
                    smoke_suppressed = False
                # Collect keywords from all models in this unit
                for model in (getattr(u, "models", []) or []):
                    try:
                        for k in (getattr(model, "keywords", []) or []):
                            ks = str(k)
                            lk = ks.lower()
                            if hover_active and lk == "aircraft":
                                continue
                            if smoke_suppressed and lk == "smoke":
                                continue
                            if lk in removed_keywords:
                                continue
                            if lk in seen:
                                continue
                            seen.add(lk)
                            kws.append(ks)
                    except Exception:
                        continue
                # Also include unit-level keywords for backwards compatibility
                for k in (getattr(u, "keywords", []) or []):
                    ks = str(k)
                    lk = ks.lower()
                    if hover_active and lk == "aircraft":
                        continue
                    if smoke_suppressed and lk == "smoke":
                        continue
                    if lk in removed_keywords:
                        continue
                    if lk in seen:
                        continue
                    seen.add(lk)
                    kws.append(ks)
                if isinstance(sr, dict):
                    extra = list(sr.get("ability_added_keywords", []) or [])
                else:
                    extra = []
                for k in extra:
                    ks = str(k)
                    lk = ks.lower()
                    if smoke_suppressed and lk == "smoke":
                        continue
                    if lk in removed_keywords:
                        continue
                    if lk in seen:
                        continue
                    seen.add(lk)
                    kws.append(ks)
                try:
                    from ...rules.adeptus_mechanicus_canticles import (
                        KEY_MANTRA_OF_DISCIPLINE,
                        unit_has_active_canticles,
                    )

                    if bool(unit_has_active_canticles(u, KEY_MANTRA_OF_DISCIPLINE)):
                        if "battleline" not in removed_keywords and "battleline" not in seen:
                            seen.add("battleline")
                            kws.append("Battleline")
                except Exception:
                    pass
                if isinstance(sr, dict) and bool(sr.get("enhancement_hero_of_the_chapter", False)):
                    keyword = str(sr.get("enhancement_hero_of_the_chapter_keyword", "BATTLELINE") or "BATTLELINE").strip()
                    keyword_lower = keyword.lower()
                    if keyword and keyword_lower not in removed_keywords:
                        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
                        bearer_alive = False
                        if bearer_id:
                            for model in list(getattr(u, "models", []) or []):
                                model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                                if model_id != bearer_id:
                                    continue
                                alive_attr = getattr(model, "is_alive", True)
                                bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                                break
                        else:
                            get_bearer = getattr(u, "_get_enhancement_bearer_model", None)
                            if callable(get_bearer):
                                bearer = get_bearer()
                                if bearer is not None:
                                    alive_attr = getattr(bearer, "is_alive", True)
                                    bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                        is_leading = False
                        attached_to = getattr(u, "attached_to", None)
                        if attached_to is not None:
                            for attached_model in list(getattr(attached_to, "models", []) or []):
                                attached_alive = getattr(attached_model, "is_alive", True)
                                if bool(attached_alive() if callable(attached_alive) else attached_alive):
                                    is_leading = True
                                    break
                        if bearer_alive and is_leading and keyword_lower not in seen:
                            seen.add(keyword_lower)
                            kws.append(keyword)
            except Exception:
                continue
        return kws

    def get_effective_faction_keywords(self) -> List[str]:
        """Effective faction keywords while attached (union of all members and all models)."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            members = root.get_attached_unit_members()
        except Exception:
            members = [self]
        kws: list[str] = []
        seen: set[str] = set()
        for u in members:
            try:
                disciple_active = False
                try:
                    if u._disciple_of_khorne_active(bodyguard=root):
                        disciple_active = True
                except Exception:
                    disciple_active = False
                # Collect faction keywords from all models in this unit
                for model in (getattr(u, "models", []) or []):
                    try:
                        for k in (getattr(model, "faction_keywords", []) or []):
                            ks = str(k)
                            lk = ks.lower()
                            if disciple_active and lk == "world eaters":
                                continue
                            if lk in seen:
                                continue
                            seen.add(lk)
                            kws.append(ks)
                    except Exception:
                        continue
                # Also include unit-level faction keywords for backwards compatibility
                for k in (getattr(u, "faction_keywords", []) or []):
                    ks = str(k)
                    lk = ks.lower()
                    if disciple_active and lk == "world eaters":
                        continue
                    if lk in seen:
                        continue
                    seen.add(lk)
                    kws.append(ks)
                if disciple_active and "blood legions" not in seen:
                    seen.add("blood legions")
                    kws.append("Blood Legions")
            except Exception:
                continue
        return kws

    def max_attached_leaders(self) -> int:
        """
        Default 10e: one Leader per Bodyguard unit.
        Some datasheets allow two Leaders; we detect common phrasing in abilities as a best-effort.
        """
        # Leaders can't have leaders attached "to" them in core rules; treat as 0/1 only on bodyguard.
        try:
            if self.is_leader:
                return 0
        except Exception:
            pass
        bodyguard_spec = self._get_bodyguard_two_leader_spec()
        if bodyguard_spec is not None:
            min_starting_strength = int(bodyguard_spec.get("min_starting_strength", 0) or 0)
            if self._starting_model_count_for_attachment_rules() >= min_starting_strength:
                return 2
            return 1
        max_leaders = 1
        try:
            for ab in getattr(self, "possible_abilities", []) or []:
                text = (getattr(ab, "description", "") or "").lower()
                if ("up to 2 leaders" in text) or ("up to two leaders" in text):
                    max_leaders = 2
                    break
                if ("can be attached to this unit even if another leader is already attached" in text):
                    max_leaders = 2
                    break
        except Exception:
            pass
        return max_leaders

    def _starting_model_count_for_attachment_rules(self) -> int:
        raw = getattr(self, "starting_model_count", None)
        if raw is None:
            raw = len(list(getattr(self, "models", []) or []))
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = len(list(getattr(self, "models", []) or []))
        return max(0, value)

    def _iter_possible_ability_name_desc_pairs(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for ab in list(getattr(self, "possible_abilities", []) or []):
            if isinstance(ab, str):
                name = str(ab or "")
                desc = str(ab or "")
            elif isinstance(ab, dict):
                name = str(ab.get("name", "") or "")
                desc = str(ab.get("description", "") or "")
            else:
                name = str(getattr(ab, "name", "") or "")
                desc = str(getattr(ab, "description", "") or "")
            pairs.append((name, desc))
        return pairs

    def _get_bodyguard_two_leader_spec(self) -> Optional[dict]:
        for name, desc in self._iter_possible_ability_name_desc_pairs():
            normalized_desc = self._normalize_rules_text(desc).lower()
            match = _BODYGUARD_TWO_LEADER_RE.search(normalized_desc)
            if match is None:
                continue
            normalized_name = self._normalize_rules_text(name).lower()
            if "bodyguard" not in normalized_name and "bodyguard" not in normalized_desc:
                continue
            min_starting_strength = int(match.group("min"))
            return {
                "min_starting_strength": int(min_starting_strength),
                "requires_warboss": "warboss unit" in normalized_desc,
                "requires_unique_leaders": _BODYGUARD_NO_DUPLICATE_LEADERS_RE.search(normalized_desc) is not None,
            }
        return None

    @staticmethod
    def _leader_has_keyword_for_attachment(leader: "Unit", keyword: str) -> bool:
        has_any = getattr(leader, "has_any_keyword", None)
        if callable(has_any) and bool(has_any(keyword)):
            return True
        has_kw = getattr(leader, "has_keyword", None)
        if callable(has_kw) and bool(has_kw(keyword)):
            return True
        return False

    @staticmethod
    def _leader_duplicate_key_for_attachment(leader: "Unit") -> str:
        if leader is None:
            return ""
        datasheet_id = ""
        get_dsid = getattr(leader, "get_datasheet_id", None)
        if callable(get_dsid):
            raw_id = get_dsid()
            datasheet_id = str(raw_id or "").strip()
        if datasheet_id:
            return f"id:{datasheet_id}"
        name = str(getattr(leader, "name", "") or "").strip().lower()
        if name:
            return f"name:{name}"
        return ""

    def _leader_attachment_constraint_error(
        self,
        candidate_leader: "Unit",
        *,
        current_leaders: Optional[list["Unit"]] = None,
    ) -> str:
        spec = self._get_bodyguard_two_leader_spec()
        leaders = list(current_leaders or list(getattr(self, "attached_leaders", []) or []))
        if candidate_leader not in leaders:
            leaders.append(candidate_leader)
        if self._bodyguard_has_masters_of_the_maelstrom_joined_support():
            if not self._is_huron_blackheart_unit_for_attachment(candidate_leader):
                return (
                    f"Unit '{self.name}' can only have Huron Blackheart attached while joined by "
                    "MASTERS OF THE MAELSTROM."
                )
        if self._bodyguard_has_heroes_of_ultramar_joined_support():
            if not self._is_captain_titus_unit_for_attachment(candidate_leader):
                return (
                    f"Unit '{self.name}' can only have Captain Titus attached while joined by "
                    "HEROES OF ULTRAMAR."
                )
        if spec is None:
            return ""
        if len(leaders) <= 1:
            return ""

        min_starting_strength = int(spec.get("min_starting_strength", 0) or 0)
        if self._starting_model_count_for_attachment_rules() < min_starting_strength:
            return (
                f"Unit '{self.name}' can only have two Leaders attached if its Starting Strength is "
                f"{min_starting_strength}."
            )

        if bool(spec.get("requires_warboss", False)):
            has_warboss = any(self._leader_has_keyword_for_attachment(leader, "WARBOSS") for leader in leaders)
            if not has_warboss:
                return (
                    f"Unit '{self.name}' requires one attached Leader with the WARBOSS keyword when attaching two Leaders."
                )
        if bool(spec.get("requires_unique_leaders", False)):
            seen: set[str] = set()
            for leader in leaders:
                key = self._leader_duplicate_key_for_attachment(leader)
                if not key:
                    continue
                if key in seen:
                    return (
                        f"Unit '{self.name}' requires attached Leaders to be different datasheets when attaching two Leaders."
                    )
                seen.add(key)
        return ""

    def _is_huron_blackheart_unit_for_attachment(self, leader: "Unit") -> bool:
        if leader is None:
            return False
        name = _normalize_unit_name_for_rules(getattr(leader, "name", "") or "")
        if name == "huron blackheart":
            return True
        get_dsid = getattr(leader, "get_datasheet_id", None)
        if callable(get_dsid):
            dsid = str(get_dsid() or "").strip()
            if dsid and dsid == _HURON_BLACKHEART_DATASHEET_ID:
                return True
        return False

    def _is_captain_titus_unit_for_attachment(self, leader: "Unit") -> bool:
        if leader is None:
            return False
        name = _normalize_unit_name_for_rules(getattr(leader, "name", "") or "")
        if name == "captain titus":
            return True
        get_dsid = getattr(leader, "get_datasheet_id", None)
        if callable(get_dsid):
            dsid = str(get_dsid() or "").strip()
            if dsid and dsid == _CAPTAIN_TITUS_DATASHEET_ID:
                return True
        return False

    def _bodyguard_has_masters_of_the_maelstrom_joined_support(self) -> bool:
        supports = list(getattr(self, "attached_support_units", []) or [])
        for support in supports:
            if support is None:
                continue
            kind_fn = getattr(support, "_joined_support_rule_kind", None)
            kind = str(kind_fn() or "").strip().lower() if callable(kind_fn) else ""
            if kind == "masters_of_the_maelstrom":
                return True
        return False

    def _bodyguard_has_heroes_of_ultramar_joined_support(self) -> bool:
        supports = list(getattr(self, "attached_support_units", []) or [])
        for support in supports:
            if support is None:
                continue
            kind_fn = getattr(support, "_joined_support_rule_kind", None)
            kind = str(kind_fn() or "").strip().lower() if callable(kind_fn) else ""
            if kind == "heroes_of_ultramar":
                return True
        return False

    def has_support_artillery_ability(self) -> bool:
        """True if this unit has the Support Artillery join rule."""
        try:
            for ab in getattr(self, "possible_abilities", []) or []:
                name = str(getattr(ab, "name", "") or "").strip().lower()
                if name == "support artillery":
                    return True
                desc = str(getattr(ab, "description", "") or "").lower()
                if (
                    "declare battle formations" in desc
                    and "guardian defenders" in desc
                    and "support weapon model" in desc
                ):
                    return True
        except Exception:
            pass
        return False

    def has_cryptek_retinue_ability(self) -> bool:
        """True if this unit has the Necron CRYPTEK RETINUE join rule."""
        try:
            for ab in getattr(self, "possible_abilities", []) or []:
                name = str(getattr(ab, "name", "") or "").strip().lower()
                if name == "cryptek retinue":
                    return True
                desc = str(getattr(ab, "description", "") or "").lower()
                if (
                    "declare battle formations" in desc
                    and "being led by a cryptek infantry model" in desc
                    and "cryptothralls" in desc
                ):
                    return True
        except Exception:
            pass
        return False

    def has_canoptek_retinue_ability(self) -> bool:
        """True if this unit has the Necron CANOPTEK RETINUE join rule."""
        try:
            for ab in getattr(self, "possible_abilities", []) or []:
                name = str(getattr(ab, "name", "") or "").strip().lower()
                if name == "canoptek retinue":
                    return True
                desc = str(getattr(ab, "description", "") or "").lower()
                if (
                    "declare battle formations" in desc
                    and "being led by a cryptek model" in desc
                    and "tomb crawlers" in desc
                ):
                    return True
        except Exception:
            pass
        return False

    def has_loyal_protector_ability(self) -> bool:
        """True if this unit has the Astra Militarum LOYAL PROTECTOR mandatory join rule."""
        try:
            for ab in getattr(self, "possible_abilities", []) or []:
                name = str(getattr(ab, "name", "") or "").strip().lower()
                if name == "loyal protector":
                    return True
                desc = str(getattr(ab, "description", "") or "").lower().replace("\u2019", "'")
                if (
                    "declare battle formations" in desc
                    and "must join one command squad unit from your army" in desc
                    and "loyal protector model joined to it" in desc
                ):
                    return True
        except Exception:
            pass
        return False

    def has_masters_of_the_maelstrom_ability(self) -> bool:
        """True if this unit has the CSM MASTERS OF THE MAELSTROM joined-support join rule."""
        try:
            for ab in getattr(self, "possible_abilities", []) or []:
                name = str(getattr(ab, "name", "") or "").strip().lower()
                if name == "masters of the maelstrom":
                    return True
                desc = str(getattr(ab, "description", "") or "").lower().replace("\u2019", "'")
                if (
                    "declare battle formations" in desc
                    and "this unit cannot join an attached unit" in desc
                    and "only huron blackheart can join a unit this unit has joined" in desc
                ):
                    return True
        except Exception:
            pass
        return False

    def has_heroes_of_ultramar_ability(self) -> bool:
        """True if this unit has the SM HEROES OF ULTRAMAR joined-support join rule."""
        try:
            for ab in getattr(self, "possible_abilities", []) or []:
                name = str(getattr(ab, "name", "") or "").strip().lower()
                if name == "heroes of ultramar":
                    return True
                desc = str(getattr(ab, "description", "") or "").lower().replace("\u2019", "'")
                if (
                    "declare battle formations" in desc
                    and "this unit cannot join an attached unit" in desc
                    and "only captain titus can join a unit this unit has joined" in desc
                ):
                    return True
        except Exception:
            pass
        return False

    def has_joined_support_ability(self) -> bool:
        """True if this unit can join another unit via joined-support style rules."""
        return bool(
            self.has_support_artillery_ability()
            or self.has_cryptek_retinue_ability()
            or self.has_canoptek_retinue_ability()
            or self.has_loyal_protector_ability()
            or self.has_masters_of_the_maelstrom_ability()
            or self.has_heroes_of_ultramar_ability()
        )

    def _joined_support_rule_kind(self) -> str:
        """
        Return joined-support rule discriminator:
        - support_artillery
        - cryptek_retinue
        - canoptek_retinue
        - loyal_protector
        - masters_of_the_maelstrom
        - heroes_of_ultramar
        - "" (no joined-support rule)
        """
        if self.has_support_artillery_ability():
            return "support_artillery"
        if self.has_cryptek_retinue_ability():
            return "cryptek_retinue"
        if self.has_canoptek_retinue_ability():
            return "canoptek_retinue"
        if self.has_loyal_protector_ability():
            return "loyal_protector"
        if self.has_masters_of_the_maelstrom_ability():
            return "masters_of_the_maelstrom"
        if self.has_heroes_of_ultramar_ability():
            return "heroes_of_ultramar"
        return ""

    def joined_support_requires_attachment(self) -> bool:
        """True if this joined-support rule is mandatory during Declare Battle Formations."""
        return str(self._joined_support_rule_kind() or "").strip().lower() == "loyal_protector"

    def _is_command_squad_unit(self, bodyguard: "Unit") -> bool:
        if bodyguard is None:
            return False
        name = _normalize_unit_name_for_rules(getattr(bodyguard, "name", "") or "")
        if "command squad" in name:
            return True
        has_local = getattr(bodyguard, "has_any_keyword_local", None)
        if callable(has_local):
            try:
                if bool(has_local("COMMAND SQUAD")):
                    return True
            except Exception:
                pass
            try:
                if bool(has_local("COMMAND")) and bool(has_local("SQUAD")):
                    return True
            except Exception:
                pass
        return False

    def _is_masters_of_the_maelstrom_target_unit(self, bodyguard: "Unit") -> bool:
        if bodyguard is None:
            return False
        name = _normalize_unit_name_for_rules(getattr(bodyguard, "name", "") or "")
        return name in _MASTERS_OF_THE_MAELSTROM_TARGET_UNIT_NAMES

    def _is_heroes_of_ultramar_target_unit(self, bodyguard: "Unit") -> bool:
        if bodyguard is None:
            return False
        name = _normalize_unit_name_for_rules(getattr(bodyguard, "name", "") or "")
        return name in _HEROES_OF_ULTRAMAR_TARGET_UNIT_NAMES

    def has_support_weapon_ability(self) -> bool:
        """True if this unit has the Support Weapon toughness override rule."""
        try:
            for ab in getattr(self, "possible_abilities", []) or []:
                name = str(getattr(ab, "name", "") or "").strip().lower()
                if name == "support weapon":
                    return True
                desc = str(getattr(ab, "description", "") or "").lower()
                if (
                    "toughness characteristic of 3" in desc
                    and "attack targets this model" in desc
                ):
                    return True
        except Exception:
            pass
        return False

    def has_empyric_ambush(self) -> bool:
        """True if an attached leader grants Empyric Ambush (charge after Flickerjump)."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "empyric_ambush"
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))

        found = False
        for ab, leader in root._iter_attached_leader_leading_abilities():
            try:
                if isinstance(ab, str):
                    name = ab
                    desc = ab
                else:
                    name = str(getattr(ab, "name", "") or "")
                    desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                continue
            text_src = leader._strip_eligibility_prefix(desc or name or "")
            normalized = leader._normalize_rules_text(text_src)
            if not normalized:
                continue
            normalized = normalized.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if root._EMPYRIC_AMBUSH_RE.search(normalized):
                found = True
                break

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = bool(found)
        root._ability_cache = cache
        return bool(found)

    def has_unique_model_restriction(self) -> bool:
        """True if this unit has a 'one-of' army inclusion restriction."""
        cache_key = "unique_model_restriction"
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return bool(cache.get(cache_key))

        found = False
        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text = self._normalize_rules_text(desc or name or "")
            if not text:
                continue
            normalized = text.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not normalized:
                continue
            if self._UNIQUE_MODEL_RESTRICTION_RE.search(normalized):
                found = True
                break
            named_match = self._UNIQUE_NAMED_MODEL_RESTRICTION_RE.search(normalized)
            if not named_match:
                continue
            named_model_key = _normalize_unit_name_for_rules(str(named_match.group("model") or ""))
            unit_key = _normalize_unit_name_for_rules(getattr(self, "name", ""))
            if named_model_key and unit_key and named_model_key == unit_key:
                found = True
                break

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = bool(found)
        self._ability_cache = cache
        return bool(found)

    def normalize_unit_name_for_rules(self, value: str) -> str:
        return _normalize_unit_name_for_rules(value)

    def get_named_unit_inclusion_caps(self) -> list[dict]:
        """
        Parse ability text for named unit caps in the form:
        "your army cannot include more than X <named unit> unit(s)".
        """
        cache_key = "named_unit_inclusion_caps"
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return [dict(entry) for entry in list(cache.get(cache_key) or [])]

        caps_by_key: dict[str, dict] = {}
        for name, desc in self._iter_ability_entries_for_rules(model=None):
            text = self._normalize_rules_text(desc or name or "")
            if not text:
                continue
            normalized = text.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not normalized:
                continue

            for match in _NAMED_UNIT_INCLUSION_LIMIT_RE.finditer(normalized):
                raw_limit = str(match.group("limit") or "").strip().lower()
                if not raw_limit:
                    continue
                if raw_limit.isdigit():
                    limit = int(raw_limit)
                else:
                    limit = _NAMED_UNIT_LIMIT_WORD_TO_INT.get(raw_limit)
                if limit is None or int(limit) <= 0:
                    continue

                raw_unit_name = str(match.group("unit") or "").strip()
                unit_key = _normalize_unit_name_for_rules(raw_unit_name)
                if not unit_key:
                    continue

                existing = caps_by_key.get(unit_key)
                if existing is None or int(existing.get("limit", 0)) > int(limit):
                    caps_by_key[unit_key] = {
                        "unit_key": unit_key,
                        "unit_name": raw_unit_name,
                        "limit": int(limit),
                    }

        caps = [caps_by_key[key] for key in sorted(caps_by_key)]
        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = [dict(entry) for entry in caps]
        self._ability_cache = cache
        return [dict(entry) for entry in caps]

    def get_inspiring_commander_specs(self) -> list[dict]:
        """
        Parse abilities like:
        "If you include this model in your army, until the end of the battle,
        non-CHARACTER models in <named unit> units from your army have an
        Objective Control characteristic of <N> while they are not Battle-shocked."
        """
        cache_key = "inspiring_commander_specs"
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return [dict(entry) for entry in list(cache.get(cache_key) or [])]

        specs_by_key: dict[tuple[int, tuple[str, ...]], dict] = {}
        for ab in list(getattr(self, "possible_abilities", []) or []):
            if isinstance(ab, str):
                name = str(ab or "")
                desc = str(ab or "")
            else:
                name = str(getattr(ab, "name", "") or "")
                desc = str(getattr(ab, "description", "") or "")
            text = self._normalize_rules_text(desc or name or "")
            if not text:
                continue
            normalized = text.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if not normalized:
                continue

            for match in _INSPIRING_COMMANDER_OC_SET_RE.finditer(normalized):
                try:
                    oc_value = int(match.group("value"))
                except (TypeError, ValueError):
                    continue
                if oc_value < 0:
                    continue

                unit_clause = str(match.group("units") or "").strip()
                if not unit_clause:
                    continue
                target_unit_names = _split_named_unit_list(unit_clause)
                target_unit_keys = sorted(
                    {
                        _normalize_unit_name_for_rules(unit_name)
                        for unit_name in target_unit_names
                        if _normalize_unit_name_for_rules(unit_name)
                    }
                )
                if not target_unit_keys:
                    continue

                key = (int(oc_value), tuple(target_unit_keys))
                existing = specs_by_key.get(key)
                if existing is None:
                    source_name = str(name or "Inspiring Commander").strip() or "Inspiring Commander"
                    specs_by_key[key] = {
                        "source": source_name,
                        "objective_control": int(oc_value),
                        "target_unit_keys": list(target_unit_keys),
                        "target_unit_names": list(target_unit_names),
                        "non_character_only": True,
                        "while_not_battle_shocked": True,
                    }
                else:
                    existing_names = set(str(v or "").strip() for v in list(existing.get("target_unit_names") or []))
                    for unit_name in target_unit_names:
                        candidate = str(unit_name or "").strip()
                        if candidate and candidate not in existing_names:
                            existing_names.add(candidate)
                    existing["target_unit_names"] = sorted(existing_names)

        specs = [specs_by_key[key] for key in sorted(specs_by_key, key=lambda item: (item[0], item[1]))]
        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = [dict(entry) for entry in specs]
        self._ability_cache = cache
        return [dict(entry) for entry in specs]

    def _get_crewed_platform_spec(self) -> Optional[dict]:
        """Return parsed crewed platform ability info, or None if not present."""
        cache_key = "crewed_platform_spec"
        cache = getattr(self, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return cache.get(cache_key)

        spec = None
        for ab in getattr(self, "possible_abilities", []) or []:
            name = str(getattr(ab, "name", "") or "")
            desc = str(getattr(ab, "description", "") or "") or name
            text_src = self._normalize_rules_text(desc or "")
            if not text_src:
                continue
            normalized = text_src.replace("\u2019", "'").replace("\u0192?T", "'")
            normalized = normalized.lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            m = self._CREWED_PLATFORM_RE.fullmatch(normalized)
            if not m:
                continue
            crew = str(m.group("crew") or "").strip()
            platform = str(m.group("platform") or "").strip()
            platform = platform.replace("serpents ", "serpent s ")
            if crew and platform:
                spec = {
                    "crew": crew,
                    "platform": platform,
                    "source": str(name or "Crewed Platform").strip() or "Crewed Platform",
                }
            break

        if not isinstance(cache, dict):
            cache = {}
        cache[cache_key] = spec
        self._ability_cache = cache
        return spec

    def _maybe_handle_crewed_platform(self, model: Optional[Model], game_map: Optional['Map'] = None) -> None:
        """Crewed Platform: destroy platform models when last crew model dies."""
        if model is None:
            return
        spec = self._get_crewed_platform_spec()
        if not spec:
            return

        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if sr.get("crewed_platform_resolved", False):
            return

        crew_key = str(spec.get("crew", "") or "").strip()
        platform_key = str(spec.get("platform", "") or "").strip()
        if not crew_key or not platform_key:
            return

        def _is_role(m: Model, role: str) -> bool:
            return self._normalize_model_name(getattr(m, "name", "")) == role

        models = list(getattr(self, "models", []) or [])
        crew_present = any(_is_role(m, crew_key) for m in models)
        if not crew_present:
            return

        alive_crew = [
            m for m in models
            if _is_role(m, crew_key) and getattr(m, "is_alive", False) and not getattr(m, "_pending_placement", False)
        ]
        if alive_crew:
            return

        platform_models = [
            m for m in models
            if _is_role(m, platform_key) and getattr(m, "is_alive", False) and not getattr(m, "_pending_placement", False)
        ]
        if not platform_models:
            return

        sr["crewed_platform_resolved"] = True
        self.special_rules = sr

        for platform_model in list(platform_models):
            platform_model.wounds = 0
            platform_model.die(game_map=game_map)

    def _support_weapon_has_other_models(self) -> bool:
        """Return True if this Support Weapon model's unit contains other models."""
        try:
            if not self.has_support_weapon_ability():
                return False
        except Exception:
            return False
        try:
            unit_models = [
                m for m in list(getattr(self, "models", []) or [])
                if getattr(m, "is_alive", True) and not getattr(m, "_pending_placement", False)
            ]
        except Exception:
            unit_models = []
        unit_alive = len(unit_models)
        if unit_alive <= 0:
            return False
        if unit_alive >= 2:
            return True
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is self:
            return False
        try:
            all_models = [
                m for m in list(root.get_attached_unit_models() or [])
                if getattr(m, "is_alive", True) and not getattr(m, "_pending_placement", False)
            ]
        except Exception:
            all_models = unit_models
        return len(all_models) > unit_alive

    def is_guardian_defenders_unit(self) -> bool:
        try:
            return str(getattr(self, "name", "") or "").strip().lower() == "guardian defenders"
        except Exception:
            return False

    def _unit_has_local_keyword(self, unit: "Unit", keyword: str) -> bool:
        if unit is None:
            return False
        try:
            has_local = getattr(unit, "has_any_keyword_local", None)
            if callable(has_local):
                return bool(has_local(keyword))
        except Exception:
            return False
        return False

    def _bodyguard_is_led_by_keywords(self, bodyguard: "Unit", required_keywords: tuple[str, ...]) -> bool:
        if bodyguard is None:
            return False
        leaders = list(getattr(bodyguard, "attached_leaders", []) or [])
        if not leaders:
            return False
        for leader in leaders:
            if leader is None:
                continue
            if all(self._unit_has_local_keyword(leader, kw) for kw in required_keywords):
                return True
        return False

    def can_join_support_artillery(self, bodyguard: "Unit") -> bool:
        """Validate joined-support eligibility (Support Artillery / Necron Retinues)."""
        if bodyguard is None or bodyguard is self:
            return False
        rule_kind = self._joined_support_rule_kind()
        if not rule_kind:
            return False
        # Same army
        try:
            if self.get_parent_army() is None or bodyguard.get_parent_army() is None:
                return False
            if self.get_parent_army() != bodyguard.get_parent_army():
                return False
        except Exception:
            return False
        # Don't allow joining a leader unit
        try:
            if bool(getattr(bodyguard, "is_leader", False)):
                return False
        except Exception:
            pass
        if rule_kind == "support_artillery":
            # Only Guardian Defenders can be joined by Support Artillery.
            if not bodyguard.is_guardian_defenders_unit():
                return False
        elif rule_kind == "cryptek_retinue":
            # CRYPTEK RETINUE: target must be led by a Cryptek Infantry model.
            if not self._bodyguard_is_led_by_keywords(bodyguard, ("Cryptek", "Infantry")):
                return False
        elif rule_kind == "canoptek_retinue":
            # CANOPTEK RETINUE: target must be led by a Cryptek model.
            if not self._bodyguard_is_led_by_keywords(bodyguard, ("Cryptek",)):
                return False
        elif rule_kind == "loyal_protector":
            # LOYAL PROTECTOR: must join one Command Squad unit.
            if not self._is_command_squad_unit(bodyguard):
                return False
        elif rule_kind == "masters_of_the_maelstrom":
            if not self._is_masters_of_the_maelstrom_target_unit(bodyguard):
                return False
            if list(getattr(bodyguard, "attached_leaders", []) or []):
                return False
        elif rule_kind == "heroes_of_ultramar":
            if not self._is_heroes_of_ultramar_target_unit(bodyguard):
                return False
            if list(getattr(bodyguard, "attached_leaders", []) or []):
                return False
        else:
            return False

        # Keep one joined support unit per bodyguard in engine state.
        try:
            supports = list(getattr(bodyguard, "attached_support_units", []) or [])
        except Exception:
            supports = []
        if supports and self not in supports:
            return False
        return True

    def attach_support_artillery_to(self, bodyguard: "Unit") -> None:
        """Join this unit to a bodyguard via joined-support rules."""
        if not self.can_join_support_artillery(bodyguard):
            raise ValueError(f"Joined support unit '{self.name}' cannot join '{getattr(bodyguard, 'name', 'Unknown')}'.")
        # Detach from any prior bodyguard first
        current = getattr(self, "support_joined_to", None)
        if current is not None and current is not bodyguard:
            self.detach_support_artillery()
        # Attach
        self.support_joined_to = bodyguard
        try:
            supports = list(getattr(bodyguard, "attached_support_units", []) or [])
        except Exception:
            supports = []
        if self not in supports:
            supports.append(self)
        bodyguard.attached_support_units = supports
        # Refresh caches
        try:
            self._invalidate_ability_cache()
        except Exception:
            pass
        try:
            bodyguard._invalidate_ability_cache()
        except Exception:
            pass

    def detach_support_artillery(self) -> None:
        """Detach this joined-support unit from its bodyguard (if any)."""
        bodyguard = getattr(self, "support_joined_to", None)
        if bodyguard is None:
            return
        try:
            supports = list(getattr(bodyguard, "attached_support_units", []) or [])
        except Exception:
            supports = []
        if self in supports:
            supports.remove(self)
        bodyguard.attached_support_units = supports
        self.support_joined_to = None
        try:
            self._invalidate_ability_cache()
        except Exception:
            pass
        try:
            bodyguard._invalidate_ability_cache()
        except Exception:
            pass

    def _normalize_attached_unit_name(self, text: str) -> str:
        raw = html.unescape(str(text or ""))
        raw = raw.replace("\u2019", "'").replace("\u2018", "'")
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"[^a-z0-9]+", " ", raw.lower())
        return re.sub(r"\s+", " ", raw).strip()

    def _leader_can_attach_to_unit_name(self, unit_name: str) -> bool:
        target = self._normalize_attached_unit_name(unit_name)
        if not target:
            return False
        names = getattr(self, "can_be_attached_to_names", []) or []
        for name in names:
            if self._normalize_attached_unit_name(name) == target:
                return True
        army = self.get_parent_army()
        if army is None:
            return False
        allowed = set(getattr(self, "can_be_attached_to", []) or [])
        for unit in list(getattr(army, "units", []) or []):
            try:
                dsid = unit.get_datasheet_id()
            except Exception:
                dsid = None
            if not dsid or dsid not in allowed:
                continue
            if self._normalize_attached_unit_name(getattr(unit, "name", "")) == target:
                return True
        return False

    def _parse_attached_unit_rule(self, text: str) -> tuple[list[str], list[str], list[str]]:
        cleaned = html.unescape(str(text or ""))
        cleaned = cleaned.replace("\u2019", "'").replace("\u2018", "'")
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            return [], [], []

        match = re.search(
            r"if a (.+?) (?:model|unit) from your army.*?can be attached to (.+)",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r"if a (.+?) from your army.*?can be attached to (.+)",
                cleaned,
                flags=re.IGNORECASE,
            )
        if not match:
            return [], [], []

        leader_clause = match.group(1)
        base_clause = match.group(2)

        base_clause = re.split(r"\bit can\b", base_clause, maxsplit=1, flags=re.IGNORECASE)[0]
        base_clause = base_clause.split(".", 1)[0].strip()
        base_names: list[str] = []
        for part in re.split(r"\bor\b", base_clause, flags=re.IGNORECASE):
            part = part.strip(" ,;.")
            part = re.sub(r"^(?:an?|the)\s+", "", part, flags=re.IGNORECASE)
            part = re.sub(r"\bunit\b\s*$", "", part, flags=re.IGNORECASE)
            part = part.strip(" ,;.")
            if part:
                base_names.append(part)

        excluded: list[str] = []
        excl_match = re.search(r"excluding\s+([^)]+)", leader_clause, flags=re.IGNORECASE)
        if excl_match:
            excl_clause = excl_match.group(1)
            excluded = [
                token.strip().upper()
                for token in re.split(r"\bor\b|\band\b|,", excl_clause, flags=re.IGNORECASE)
                if token.strip()
            ]
            leader_clause = leader_clause[:excl_match.start()].strip()

        leader_clause = re.sub(r"\bunit\b|\bmodel\b", "", leader_clause, flags=re.IGNORECASE)
        leader_clause = leader_clause.replace("(", " ").replace(")", " ")
        leader_clause = re.sub(r"\s+", " ", leader_clause).strip()
        leader_keywords = [
            token.strip().upper()
            for token in re.split(r"\bor\b|\band\b|,", leader_clause, flags=re.IGNORECASE)
            if token.strip()
        ]

        return leader_keywords, base_names, excluded

    def _can_attach_via_attached_unit_rule(self, bodyguard: "Unit") -> bool:
        if bodyguard is None:
            return False
        abilities = list(getattr(bodyguard, "possible_abilities", []) or [])
        for ab in abilities:
            try:
                name = ab if isinstance(ab, str) else getattr(ab, "name", "")
            except Exception:
                name = ""
            if "attached unit" not in str(name or "").lower():
                continue
            try:
                desc = ab if isinstance(ab, str) else getattr(ab, "description", "")
            except Exception:
                desc = ""
            leader_keywords, base_names, excluded = self._parse_attached_unit_rule(desc)
            if not base_names or not leader_keywords:
                continue
            if excluded and any(self.has_any_keyword(k) for k in excluded):
                continue
            if not any(self.has_any_keyword(k) for k in leader_keywords):
                continue
            for base_name in base_names:
                if self._leader_can_attach_to_unit_name(base_name):
                    return True
        return False

    def can_attach_to(self, bodyguard: 'Unit') -> bool:
        """Validate basic 10e attachment eligibility using Wahapedia leader linkage data."""
        if not self.is_leader:
            return False
        if bodyguard is None or bodyguard is self:
            return False
        # Same army
        try:
            if self.get_parent_army() is None or bodyguard.get_parent_army() is None:
                return False
            if self.get_parent_army() != bodyguard.get_parent_army():
                return False
        except Exception:
            return False
        army = self.get_parent_army()
        csm_mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        match_fn = getattr(csm_mgr, "pactbound_zealots_leader_marks_match", None) if csm_mgr is not None else None
        if callable(match_fn) and not bool(match_fn(self, bodyguard)):
            return False
        # Can't attach to another leader unit
        try:
            if bodyguard.is_leader:
                return False
        except Exception:
            pass
        # Disciple of Khorne: Lord on Juggernaut can attach to Bloodcrushers/Flesh Hounds.
        try:
            if self._disciple_of_khorne_can_attach_to(bodyguard):
                return True
        except Exception:
            pass
        # Butcher Lord (Cult of Blood): bearer can attach to Jakhals/Goremongers.
        try:
            if self._butcher_lord_can_attach_to(bodyguard):
                return True
        except Exception:
            pass
        # Abhuman Detail (Grizzled Company): COMMISSAR bearer can attach to Ogryn/Bullgryn.
        try:
            if self._abhuman_detail_can_attach_to(bodyguard):
                return True
        except Exception:
            pass
        # Exalted Patron (Court of the Phoenician): bearer can attach to Flawless Blades.
        try:
            if self._exalted_patron_can_attach_to(bodyguard):
                return True
        except Exception:
            pass
        # Wolf-touched (Saga of the Beastslayer): bearer can attach to Wulfen Infantry.
        try:
            if self._wolf_touched_can_attach_to(bodyguard):
                return True
        except Exception:
            pass
        # Grimnar's Mark (Saga of the Great Wolf): bearer can attach to Wolf Guard Terminators.
        try:
            if self._grimnars_mark_can_attach_to(bodyguard):
                return True
        except Exception:
            pass
        # Catechism of Divine Penitence (Penitent Host): bearer can attach to Repentia Squad.
        try:
            if self._catechism_of_divine_penitence_can_attach_to(bodyguard):
                return True
        except Exception:
            pass
        # Bodyguard datasheet id must be in leader's allowed attached_to list (IDs)
        allowed = getattr(self, "can_be_attached_to", []) or []
        try:
            bodyguard_id = bodyguard.get_datasheet_id()
        except Exception:
            bodyguard_id = None
        if not bodyguard_id:
            return False
        attach_allowed = bool(bodyguard_id in allowed or self._can_attach_via_attached_unit_rule(bodyguard))
        if not attach_allowed:
            return False

        current_leaders = list(getattr(bodyguard, "attached_leaders", []) or [])
        if self not in current_leaders:
            max_leaders = int(bodyguard.max_attached_leaders() or 0)
            if max_leaders <= 0:
                return False
            if len(current_leaders) >= max_leaders:
                return False
        error = str(bodyguard._leader_attachment_constraint_error(self, current_leaders=current_leaders) or "")
        if error:
            return False
        return True

    def attach_to_unit(self, bodyguard: 'Unit') -> None:
        """Attach this Leader to a Bodyguard unit (Declare Battle Formations)."""
        if not self.is_leader:
            raise ValueError(f"Unit '{self.name}' is not a Leader and cannot be attached.")
        if not self.can_attach_to(bodyguard):
            raise ValueError(f"Leader '{self.name}' cannot be attached to '{getattr(bodyguard, 'name', 'Unknown')}'.")
        # Enforce per-bodyguard leader limit
        max_leaders = bodyguard.max_attached_leaders()
        if max_leaders <= 0:
            raise ValueError(f"Unit '{bodyguard.name}' cannot have Leaders attached.")
        try:
            current = list(getattr(bodyguard, "attached_leaders", []) or [])
        except Exception:
            current = []
        # If already attached to this unit, no-op
        if self in current and getattr(self, "attached_to", None) is bodyguard:
            return
        if len(current) >= max_leaders:
            raise ValueError(f"Unit '{bodyguard.name}' already has the maximum number of Leaders attached ({max_leaders}).")
        constraint_error = str(bodyguard._leader_attachment_constraint_error(self, current_leaders=current) or "")
        if constraint_error:
            raise ValueError(constraint_error)
        # Detach from any prior bodyguard first
        if getattr(self, "attached_to", None) is not None and getattr(self, "attached_to", None) is not bodyguard:
            self.detach_from_unit()
        # Attach
        self.attached_to = bodyguard
        if self not in current:
            current.append(self)
        bodyguard.attached_leaders = current
        try:
            self._apply_attached_possessed_formation_bonus(bodyguard)
        except Exception:
            pass
        try:
            self._apply_attached_battleline_infiltrators_scouts(bodyguard)
        except Exception:
            pass
        try:
            self._apply_attached_unit_bodyguard_leader_scouts(bodyguard)
        except Exception:
            pass
        try:
            self._apply_attached_unit_bodyguard_leader_deep_strike(bodyguard)
        except Exception:
            pass
        # Attachment status affects leading-only abilities; refresh caches/rules.
        try:
            self._invalidate_ability_cache()
        except Exception:
            pass
        try:
            bodyguard._invalidate_ability_cache()
        except Exception:
            pass
        try:
            self._parse_against_attack_characteristic_defensive_rules()
        except Exception:
            pass
        try:
            bodyguard._parse_against_attack_characteristic_defensive_rules()
        except Exception:
            pass
        try:
            self._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            bodyguard._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            self._refresh_advance_no_roll_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_advance_no_roll_flags()
        except Exception:
            pass
        try:
            self._refresh_ignore_vertical_distance_move_types()
        except Exception:
            pass
        try:
            bodyguard._refresh_ignore_vertical_distance_move_types()
        except Exception:
            pass
        try:
            self._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            self._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass
        try:
            self._refresh_command_phase_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_command_phase_flags()
        except Exception:
            pass
        try:
            self._refresh_fall_back_desperate_escape_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_fall_back_desperate_escape_flags()
        except Exception:
            pass
        try:
            self._refresh_targeted_stratagem_cp_discount_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_targeted_stratagem_cp_discount_flags()
        except Exception:
            pass
        try:
            self._refresh_targeted_stratagem_cp_increase_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_targeted_stratagem_cp_increase_flags()
        except Exception:
            pass
        try:
            self._refresh_charge_end_mortal_wounds_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_charge_end_mortal_wounds_flags()
        except Exception:
            pass
        try:
            self._refresh_fight_within_3_flags()
        except Exception:
            pass
        try:
            bodyguard._refresh_fight_within_3_flags()
        except Exception:
            pass

    def detach_from_unit(self) -> None:
        """Detach this Leader from its Bodyguard unit."""
        if not self.is_leader:
            return
        bodyguard = getattr(self, "attached_to", None)
        if bodyguard is None:
            return
        try:
            leaders = list(getattr(bodyguard, "attached_leaders", []) or [])
            if self in leaders:
                leaders.remove(self)
            bodyguard.attached_leaders = leaders
        except Exception:
            pass
        self.attached_to = None
        try:
            self._clear_attached_unit_bodyguard_leader_scouts()
        except Exception:
            pass
        try:
            self._clear_attached_unit_bodyguard_leader_deep_strike()
        except Exception:
            pass
        # Attachment status affects leading-only abilities; refresh caches/rules.
        try:
            self._invalidate_ability_cache()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._invalidate_ability_cache()
        except Exception:
            pass
        try:
            self._parse_against_attack_characteristic_defensive_rules()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._parse_against_attack_characteristic_defensive_rules()
        except Exception:
            pass
        try:
            self._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_bearer_unit_common_modifiers()
        except Exception:
            pass
        try:
            self._refresh_advance_no_roll_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_advance_no_roll_flags()
        except Exception:
            pass
        try:
            self._refresh_ignore_vertical_distance_move_types()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_ignore_vertical_distance_move_types()
        except Exception:
            pass
        try:
            self._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_bearer_keyword_flags()
        except Exception:
            pass
        try:
            self._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_move_over_friendly_monster_vehicle_flags()
        except Exception:
            pass
        try:
            self._refresh_command_phase_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_command_phase_flags()
        except Exception:
            pass
        try:
            self._refresh_fall_back_desperate_escape_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_fall_back_desperate_escape_flags()
        except Exception:
            pass
        try:
            self._refresh_targeted_stratagem_cp_discount_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_targeted_stratagem_cp_discount_flags()
        except Exception:
            pass
        try:
            self._refresh_targeted_stratagem_cp_increase_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_targeted_stratagem_cp_increase_flags()
        except Exception:
            pass
        try:
            self._refresh_charge_end_mortal_wounds_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_charge_end_mortal_wounds_flags()
        except Exception:
            pass
        try:
            self._refresh_fight_within_3_flags()
        except Exception:
            pass
        try:
            if bodyguard is not None:
                bodyguard._refresh_fight_within_3_flags()
        except Exception:
            pass

    @property
    def is_supreme_commander(self) -> bool:
        # Wahapedia encodes this as a datasheet-sourced ability row (ability_id == ""),
        # e.g. name == "SUPREME COMMANDER".
        for ab in getattr(self, "possible_abilities", []) or []:
            if isinstance(ab, str):
                if ab.strip().upper() == "SUPREME COMMANDER":
                    return True
                continue
            name = str(getattr(ab, "name", "") or "")
            if name.strip().upper() == "SUPREME COMMANDER":
                return True
        return False

    @property
    def is_monster(self) -> bool:
        return self.has_keyword("Monster")

    @property
    def is_vehicle(self) -> bool:
        return self.has_keyword("Vehicle")

    @property
    def is_aircraft(self) -> bool:
        if bool(getattr(self, "hover_mode", False)):
            return False
        return self.has_keyword("Aircraft")

    @property
    def is_fortification(self) -> bool:
        return self.has_keyword("Fortification")

    @property
    def is_character(self) -> bool:
        return self.has_keyword("Character")

    @property
    def is_psyker(self) -> bool:
        return self.has_keyword("Psyker")

    @property
    def is_infantry(self) -> bool:
        return self.has_keyword("Infantry")

    def counts_as_infantry_for_terrain(self) -> bool:
        """Kill Team models count as Infantry for terrain interaction (RUINS traversal)."""
        if self.is_infantry:
            return True
        try:
            root = self.get_attached_unit_root()
            if root is not None and hasattr(root, "attached_unit_has_kill_team"):
                return bool(root.attached_unit_has_kill_team())
        except Exception:
            pass
        return False

    @property
    def is_beast(self) -> bool:
        return self.has_keyword("Beast")

    @property
    def is_titanic(self) -> bool:
        return self.has_keyword("Titanic")

    @property
    def is_towering(self) -> bool:
        return self.has_keyword("Towering")

    @property
    def is_flying(self) -> bool:
        return self.has_keyword("Fly")

    @property
    def is_smoke(self) -> bool:
        return self.has_keyword("Smoke")

    @property
    def is_belisarius_cawl(self) -> bool:
        return self.has_keyword("Belisarius Cawl")

    @property
    def is_imperium_primarch(self) -> bool:
        return self.has_keyword("Imperium") and self.has_keyword("Primarch")

    def has_super_heavy_walker(self) -> bool:
        """True if this unit has the Super-heavy Walker (or War Engine) ability."""
        if 'super_heavy_walker' in getattr(self, '_ability_cache', {}):
            return bool(self._ability_cache['super_heavy_walker'])

        found = False
        try:
            found, _ = self._find_ability_with_patterns(
                [
                    "super-heavy walker",
                    "super-heavy war engine",
                    "super heavy war engine",
                ]
            )
        except Exception:
            found = False

        if not found:
            try:
                checker = getattr(self, "_attached_unit_has_active_enhancement", None)
                if callable(checker):
                    found = bool(
                        checker(
                            "enhancement_houndpack_preyslayers_mantle",
                            enhancement_id="000010312002",
                            enhancement_name="Preyslayer's Mantle",
                        )
                    )
            except Exception:
                found = False

        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['super_heavy_walker'] = bool(found)
        return bool(found)

    def has_hover(self) -> bool:
        """True if this unit has the Hover core ability."""
        if 'hover' in getattr(self, '_ability_cache', {}):
            return bool(self._ability_cache['hover'])
        found = False
        for ab in self._iter_active_abilities():
            try:
                name = str(getattr(ab, "name", "") or "").strip().lower()
            except Exception:
                name = ""
            if name == "hover":
                found = True
                break
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['hover'] = bool(found)
        return bool(found)

    def set_hover_mode(self, enabled: bool) -> None:
        """Enable/disable Hover mode (Move becomes 20", AIRCRAFT keyword removed for rules)."""
        enabled = bool(enabled)
        if bool(getattr(self, "hover_mode", False)) == enabled:
            return
        self.hover_mode = enabled
        try:
            self.remove_characteristic_modifiers_by_source("hover_mode")
        except Exception:
            pass
        if enabled:
            try:
                from ...utility.modifiers import Modifier, ModifierOp
                self.add_characteristic_modifier(
                    "movement",
                    Modifier(ModifierOp.SET, 20, source="hover_mode"),
                )
            except Exception:
                pass

    def has_flip_belt(self) -> bool:
        """True if this unit has the Flip Belt ability (ignore vertical distance for certain moves)."""
        if 'flip_belt' in getattr(self, '_ability_cache', {}):
            return bool(self._ability_cache['flip_belt'])
        found = False
        try:
            if hasattr(self, "_trait_flag"):
                found = bool(self._trait_flag("flip_belt", default=False))
            if not found:
                found, _ = self._find_ability_with_patterns(["flip belt"])
        except Exception:
            found = False
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['flip_belt'] = bool(found)
        return bool(found)

    def must_start_in_reserves(self) -> bool:
        """True if this unit must start the battle in Reserves (e.g., non-hover AIRCRAFT)."""
        if bool(getattr(self, "hover_mode", False)):
            return False
        if bool(self.is_aircraft):
            return True
        get_rule = getattr(self, "get_drop_pod_assault_rule", None)
        rule = get_rule() if callable(get_rule) else None
        if isinstance(rule, dict) and bool(rule.get("requires_start_in_reserves", False)):
            return True
        return False

    def has_kill_team(self) -> bool:
        """Check if the unit has the Kill Team ability (Imperial Agents)."""
        if 'kill_team' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['kill_team']
        found = False
        try:
            if hasattr(self, "_trait_flag"):
                found = bool(self._trait_flag("kill_team", default=False))
            if not found:
                found, _ = self._find_ability_with_patterns(["kill team"])
        except Exception:
            found = False
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['kill_team'] = found
        return found
    

    def can_move_through_ruins_walls(self) -> bool:
        """Check if this unit can move through RUINS walls via Breachable-style rules."""
        return (self.counts_as_infantry_for_terrain() or self.is_beast or
                self.is_imperium_primarch or self.is_belisarius_cawl)
    

    def can_access_upper_floors(self) -> bool:
        """Check if this unit can be placed on upper floors of RUINS."""
        return (self.counts_as_infantry_for_terrain() or self.is_beast or
                self.is_imperium_primarch or self.is_belisarius_cawl or
                self.is_flying)
    

    def can_overhang_floor(self) -> bool:
        """Check if this unit's base can overhang floor edges on upper floors."""
        return False

    def has_keyword_local(self, keyword: str) -> bool:
        kw = (keyword or "").lower().strip()
        if not kw:
            return False
        try:
            return kw in [k.lower() for k in (self.keywords or [])]
        except Exception:
            return False

    def has_any_keyword_local(self, keyword: str) -> bool:
        """Case-insensitive keyword check across local keywords + faction_keywords."""
        kw = (keyword or "").lower().strip()
        if not kw:
            return False
        try:
            if kw in [k.lower() for k in (self.keywords or [])]:
                return True
        except Exception:
            pass
        try:
            if kw in [k.lower() for k in (self.faction_keywords or [])]:
                return True
        except Exception:
            pass
        return False

    def has_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").lower().strip()
        if not kw:
            return False
        try:
            return kw in [k.lower() for k in (self.get_effective_keywords() or [])]
        except Exception:
            return kw in [k.lower() for k in (self.keywords or [])]

    def has_any_keyword(self, keyword: str) -> bool:
        """Case-insensitive keyword check across keywords + faction_keywords."""
        kw = (keyword or "").lower().strip()
        if not kw:
            return False
        try:
            if kw in [k.lower() for k in (self.get_effective_keywords() or [])]:
                return True
        except Exception:
            pass
        try:
            if kw in [k.lower() for k in (self.get_effective_faction_keywords() or [])]:
                return True
        except Exception:
            pass
        return False

    def get_plasma_warhead_models(self) -> list:
        """Return alive models in this unit that have a Plasma Warhead weapon."""
        models = []
        for model in list(getattr(self, "models", []) or []):
            if not getattr(model, "is_alive", False):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                profiles = getattr(wargear, "profiles", {}) or {}
                for profile in profiles.values():
                    if bool(getattr(profile, "is_plasma_warhead", lambda: False)()):
                        models.append(model)
                        break
                if models and models[-1] is model:
                    break
        return models

    def has_plasma_warhead_weapon(self) -> bool:
        """Return True if any alive model in this unit has a Plasma Warhead weapon."""
        return bool(self.get_plasma_warhead_models())

    @property
    def movement(self) -> int:
        if not getattr(self, "models", None):
            return int(getattr(self, "_movement", 0) or 0)
        m = self.models[0]
        return int(getattr(m, "movement", getattr(m, "_movement", getattr(self, "_movement", 0))) or 0)

    @property
    def toughness(self) -> int:
        # 10e Attached Units: To Wound uses the Bodyguard's Toughness while the Leader is attached.
        try:
            if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                return int(self.attached_to.toughness)
        except Exception:
            pass

        # If bodyguard models are gone but separation is pending, preserve the last known bodyguard Toughness
        try:
            if len(self.models) == 0 and bool(getattr(self, "_pending_leader_separation", False)):
                t = getattr(self, "_last_bodyguard_toughness", None)
                if t is not None:
                    return int(t)
        except Exception:
            pass

        # Support Weapon: if this model's unit contains other models, use T3 for this model.
        try:
            if self._support_weapon_has_other_models():
                return 3
        except Exception:
            pass

        return self.models[0].toughness

    @property
    def save(self) -> int:
        return int(self.models[0].save)

    @property
    def inv_save(self) -> Optional[int]:
        return self.models[0].inv_save

    @property
    def leadership(self) -> int:
        # Best Leadership in the unit (lowest value). For Attached units, consider leaders + bodyguards.
        try:
            if bool(getattr(self, "is_leader", False)) and getattr(self, "attached_to", None) is not None:
                # Avoid double-resolution; attached leaders delegate to their bodyguard unit.
                return int(self.attached_to.leadership)
        except Exception:
            pass

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        try:
            models = root.get_models_for_collision()
        except Exception:
            models = root.models

        best = None
        for m in (models or []):
            try:
                if not getattr(m, "is_alive", True):
                    continue
                ld = int(getattr(m, "leadership"))
                best = ld if best is None else min(best, ld)
            except Exception:
                continue

        if best is not None:
            return best
        # Fallback to first model if something is off
        return self.models[0].leadership

    @property
    def objective_control(self) -> int:
        # Use the unified pipeline so DIV/MUL ordering is correct (e.g. halve then +1).
        try:
            # Call as an unbound method so this property still works when accessed via
            # `type(self).objective_control.fget(stub_unit)` in tests that use lightweight stubs.
            return int(Unit.get_effective_model_characteristic(self, self.models[0], "objective_control"))
        except Exception:
            return int(self.models[0].objective_control)

    @property
    def has_circular_base(self) -> bool:
        return self.models[0].has_circular_base

    @property
    def base_size(self) -> float:
        return self.models[0].base_size

    @property
    def model_height(self) -> float:
        return max(model.model_base.model_height for model in self.models)

    def print_unit(self):
        for model in self.models:
            logger.info(f"\n{model}")

    def get_unique_model_names(self) -> List[str]:
        return list(set(model.name for model in self.models))

    def _parse_models_cost(self, models_cost):
        """
        Parse `datasheets_models_cost` rows from Wahapedia.

        Common forms:
        - "3 models" -> "80" (base cost by model-count bucket)
        - "Attack Bike" -> "+55" (add-on model/upgrade cost)

        We store:
        - `self.models_cost`: dict[int, int] mapping model-count bucket -> points
        - `self.models_cost_addons`: dict[str, int] mapping addon label -> points (lower-cased)
        """
        import re

        base: dict[int, int] = {}
        self.models_cost_addons = {}

        for cost_entry in (models_cost or []):
            desc = str(cost_entry.get("description", "") or "").strip()
            cost_raw = str(cost_entry.get("cost", "") or "").strip()

            # Base bucket:
            # - "10 models" -> 10
            # - "1 Spanner and 4 Lootas" -> 5 (sum of all counts)
            nums = re.findall(r"\b\d+\b", desc)
            if nums:
                try:
                    if len(nums) == 1:
                        n = int(nums[0])
                    else:
                        n = sum(int(x) for x in nums)
                    base[n] = int(cost_raw.replace("+", "").strip())
                    continue
                except Exception:
                    pass

            # Add-on row: typically "+55" or "55"
            m = re.match(r"^\+?\s*(\d+)\s*$", cost_raw)
            if m and desc:
                self.models_cost_addons[desc.lower()] = int(m.group(1))

        return base

    def calculate_points(self, num_models):
        # Only consider numeric thresholds.
        numeric = [(k, v) for k, v in (self.models_cost or {}).items() if isinstance(k, int)]
        for threshold, cost in sorted(numeric, reverse=True):
            if num_models >= threshold:
                return int(cost)
        return 0

    def max_models_for_points(self, max_points):
        max_models = 0
        numeric = [(k, v) for k, v in (self.models_cost or {}).items() if isinstance(k, int)]
        for num_models, cost in sorted(numeric):
            if int(cost) <= max_points:
                max_models = int(num_models)
            else:
                break
        return max_models

    def get_unit_cost(self) -> int:
        """
        Calculate the cost of the unit based on the number of models.
        If the unit has an enhancement, add the enhancement cost to the unit cost.

        Returns:
            int: The cost of the unit in points (including enhancement cost if applicable)
        """
        num_models = len(self.models)
        total = self.calculate_points(num_models) + (self.enhancement.points if self.enhancement else 0)

        # Add-on model/upgrade costs (e.g. "Attack Bike" +55) when present.
        try:
            addons = getattr(self, "models_cost_addons", None) or {}
            if addons:
                # Count by model name, case-insensitive exact match.
                counts = {}
                for m in (self.models or []):
                    try:
                        name = str(getattr(m, "name", "") or "").strip().lower()
                        if not name:
                            continue
                        counts[name] = counts.get(name, 0) + 1
                    except Exception:
                        continue
                for addon_name, addon_cost in addons.items():
                    c = counts.get(str(addon_name).strip().lower(), 0)
                    if c:
                        total += int(addon_cost) * int(c)
        except Exception:
            pass

        army = self.get_parent_army() if hasattr(self, "get_parent_army") else getattr(self, "parent_army", None)
        ia_mgr = getattr(army, "imperial_agents_detachments", None) if army is not None else None
        surcharge_fn = getattr(ia_mgr, "extremis_sanction_points_surcharge_for_unit", None) if ia_mgr is not None else None
        if callable(surcharge_fn):
            total += int(surcharge_fn(self) or 0)
        ne_mgr = getattr(army, "necrons_detachments", None) if army is not None else None
        pantheon_surcharge_fn = getattr(ne_mgr, "pantheon_of_woe_points_surcharge_for_unit", None) if ne_mgr is not None else None
        if callable(pantheon_surcharge_fn):
            total += int(pantheon_surcharge_fn(self) or 0)

        return int(total)

    def configure_models(self, count, wargear):
        # Recreate the models with the specified count
        self.models = self._create_models(self._datasheet, count)
        self.update_coherency()

        # Apply wargear to all models
        for model in self.models:
            if wargear:
                if type(wargear) == list:
                    for wargear_item in wargear:
                        model.add_wargear(wargear_item)
                else:
                    model.add_wargear(wargear)
            else:
                model.wargear = []

    @property
    def abilities(self):
        abilities = []
        for model in self.models:
            abilities.extend(model.abilities)
        return abilities

    @property
    def health_percent(self) -> float:
        """Calculate the percentage of remaining health."""
        total_wounds = sum(model.wounds for model in self.models)
        max_wounds = sum(model._base_wounds for model in self.models)
        if max_wounds == 0:
            return 0
        return (total_wounds / max_wounds) * 100

    @property
    def is_ranged_unit(self) -> bool:
        """Determine if the unit is primarily a ranged unit."""
        # For simplicity, if the unit has more ranged weapons than melee weapons
        ranged_weapons = 0
        melee_weapons = 0
        for model in self.models:
            for weapon in model.wargear:
                if weapon.is_ranged():
                    ranged_weapons += 1
                elif weapon.is_melee():
                    melee_weapons += 1
        return ranged_weapons >= melee_weapons

    @property
    def is_melee_unit(self) -> bool:
        """Determine if the unit is primarily a melee unit."""
        return not self.is_ranged_unit()

    @property
    def max_charge_distance(self) -> float:
        """Calculate the maximum possible charge distance."""
        return 12.0  # 2D6 maximum roll

    def get_threat_level(self, target_unit: Optional['Unit'] = None) -> Tuple[float, float]:
        """Calculate the threat level of the unit based on offensive capabilities."""
        melee_threat = 0
        ranged_threat = 0
        for model in self.models:
            for weapon in model.wargear:
                if weapon.is_ranged() or weapon.is_melee():
                    dmg_potential = weapon.get_damage_potential(target_unit)
                    #print(f"{weapon.name} damage potential: {dmg_potential}")
                    if weapon.is_ranged():
                        ranged_threat += dmg_potential
                    else:
                        melee_threat += dmg_potential
                else:
                    raise Exception(f"UNHANDLED WEAPON TYPE: {weapon.name}")
        return ranged_threat, melee_threat

    def get_threat_per_cost(self, target_unit: Optional['Unit'] = None) -> Tuple[float, float]:
        ranged_threat, melee_threat = self.get_threat_level(target_unit)
        try:
            cost = self.models_cost[len(self.models)]
        except KeyError:
            try:
                cost = self.models_cost[len(self.models) - 1]
                cost += self.models_cost["extra"]
            except KeyError:
                logger.info(f"No cost found for {self.name}")
                cost = 1000
        return ranged_threat / cost, melee_threat / cost

    ###########################################################################
    ### Core Actions
    ###########################################################################

