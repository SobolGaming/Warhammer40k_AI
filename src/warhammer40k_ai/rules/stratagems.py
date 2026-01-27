import time
import copy
import html
import re
from typing import Callable, Optional, Dict, Any, List
from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id


IMPLEMENTED_STRATAGEM_NAMES = {
    "A GRIM WARNING",
    "ARMOUR OF CONTEMPT",
    "A WORTHY SKULL",
    "APOPLECTIC FRENZY",
    "BERZERKER'S WRATH",
    "BERZERKER\u2019S WRATH",
    "BLESSING OF BURNING BLOOD",
    "BLITZING FIREPOWER",
    "BLOOD OFFERING",
    "DAEMONIC FURY",
    "DAEMONTIDE",
    "DEATHLESS DUTY",
    "DEATH ECSTASY",
    "FRENZIED RESILIENCE",
    "FEIGNED RETREAT",
    "FIRE AND FADE",
    "HACK AND SLASH",
    "LIGHTNING-FAST REACTIONS",
    "LIMB FROM LIMB",
    "MURDER-CALL",
    "COMMAND RE-ROLL",
    "COUNTER-OFFENSIVE",
    "EPIC CHALLENGE",
    "FIRE OVERWATCH",
    "OVERWATCH",
    "GO TO GROUND",
    "GRENADE",
    "GILDED CHAMPION",
    "HEROIC INTERVENTION",
    "INSANE BRAVERY",
    "NEW ORDERS",
    "RAPID INGRESS",
    "SKYBORNE SANCTUARY",
    "SMOKESCREEN",
    "SKULLS FOR THE SKULL THRONE!",
    "SUMMONED BY SLAUGHTER",
    "TERRIFYING SPECTACLE",
    "TANK SHOCK",
    "THE FOE FORESEEN",
    "CUT DOWN THE WEAK",
    "UNBOUND ARROGANCE",
    "UNLEASH THE LIONS",
    "WEBWAY TUNNEL",
    "UNYIELDING FORMS",
    "MERCILESS RECLAMATION",
    "DIMENSIONAL TUNNEL",
    "CHRONOSHIFT",
    "ENDLESS SERVITUDE",
    "REACTIVE REPOSITION",
    "RED WRATH",
}

REACTION_ONLY_STRATAGEM_NAMES = {
    "A GRIM WARNING",
    "ARMOUR OF CONTEMPT",
    "A WORTHY SKULL",
    "APOPLECTIC FRENZY",
    "BERZERKER'S WRATH",
    "BERZERKER\u2019S WRATH",
    "BLESSING OF BURNING BLOOD",
    "BLOOD OFFERING",
    "CUT DOWN THE WEAK",
    "DEATHLESS DUTY",
    "DEATH ECSTASY",
    "FRENZIED RESILIENCE",
    "FEIGNED RETREAT",
    "COMMAND RE-ROLL",
    "COUNTER-OFFENSIVE",
    "FIRE OVERWATCH",
    "OVERWATCH",
    "GO TO GROUND",
    "GILDED CHAMPION",
    "HEROIC INTERVENTION",
    "INSANE BRAVERY",
    "NEW ORDERS",
    "RAPID INGRESS",
    "FIRE AND FADE",
    "MURDER-CALL",
    "LIGHTNING-FAST REACTIONS",
    "SKULLS FOR THE SKULL THRONE!",
    "SMOKESCREEN",
    "SKYBORNE SANCTUARY",
    "SUMMONED BY SLAUGHTER",
    "THE FOE FORESEEN",
    "UNBOUND ARROGANCE",
    "WEBWAY TUNNEL",
    "UNYIELDING FORMS",
    "ENDLESS SERVITUDE",
    "REACTIVE REPOSITION",
    "RED WRATH",
}


def _unit_cannot_be_target_of_stratagem(unit: Any) -> bool:
    """
    Core rule: Battle-shocked units cannot be the target of a Stratagem.

    Also: Units embarked within a Transport are not on the battlefield and cannot be targeted by rules,
    including Stratagems (unless explicitly stated otherwise).

    We treat a unit as battle-shocked if either:
    - it implements `is_battle_shocked()` and returns True, or
    - it has `special_rules['cannot_use_stratagems'] == True` (set by BattleShockEffect)

    This helper is intentionally defensive because some tests use lightweight stubs instead of full Unit objects.
    """
    if unit is None:
        return False

    # Embarked restriction: cannot target embarked units with stratagems (even INSANE BRAVERY).
    if bool(getattr(unit, "is_embarked", False)):
        return True
    if getattr(unit, "embarked_in", None) is not None:
        return True
    is_bs = getattr(unit, "is_battle_shocked", None)
    if callable(is_bs) and bool(is_bs()):
        return True
    sr = getattr(unit, "special_rules", None)
    if isinstance(sr, dict) and sr.get("cannot_use_stratagems") is True:
        return True
    return False


def _extract_friendly_target_unit_from_kwargs(kwargs: Dict[str, Any]) -> Any:
    """
    Best-effort extraction of the *friendly* unit being targeted by a stratagem.

    Notes:
    - We intentionally do NOT treat `enemy_unit` as a target, since it is typically the trigger context.
    - Multiple keys exist across special-cases (e.g. Overwatch uses `shooter_unit`).
    """
    for key in ("target_unit", "unit", "shooter_unit", "attacker_unit", "defender_unit"):
        u = kwargs.get(key)
        if u is not None:
            return u
    return None


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = text.replace("\u2019", "'")
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_token(text: str) -> str:
    t = str(text or "").lower().replace("\u2019", "'")
    t = re.sub(r"[^a-z0-9+ ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _extract_stratagem_section(description: str, label: str) -> str:
    if not description:
        return ""
    m = re.search(
        rf"<b>{re.escape(label)}:</b>(.*?)(<br><br><b>|$)",
        description,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1).strip()
    m = re.search(
        rf"\b{re.escape(label)}:\s*(.*?)(\b(WHEN|TARGET|EFFECT):|$)",
        description,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return m.group(1).strip() if m else ""


def _extract_kwb_keywords(target_html: str) -> List[str]:
    if not target_html:
        return []
    pattern = re.compile(r'<span[^>]+class="[^"]*\bkwb\w*\b[^"]*"[^>]*>(.*?)</span>', re.I | re.S)
    matches = list(pattern.finditer(target_html))
    keywords: List[str] = []
    i = 0
    while i < len(matches):
        phrase = _strip_html(matches[i].group(1))
        j = i + 1
        while j < len(matches):
            between = _strip_html(target_html[matches[j - 1].end() : matches[j].start()])
            if _normalize_token(between) == "":
                phrase = f"{phrase} {_strip_html(matches[j].group(1))}".strip()
                j += 1
                continue
            break
        if phrase:
            keywords.append(phrase)
        i = j
    out: List[str] = []
    for kw in keywords:
        if kw not in out:
            out.append(kw)
    return out


def parse_defensive_reaction_stratagem(name: str, description: str) -> Optional[Dict[str, Any]]:
    """
    Parse generic defensive stratagems that trigger after enemy target selection.

    Supported effect patterns (strict):
    - -1 to hit / -1 to wound (melee/ranged/any)
    - AP worsened by 1
    - Damage characteristic reduced by 1
    - Invulnerable save granted (X+)
    - Feel No Pain granted (X+)
    """
    if not description:
        return None

    when_html = _extract_stratagem_section(description, "WHEN")
    target_html = _extract_stratagem_section(description, "TARGET")
    effect_html = _extract_stratagem_section(description, "EFFECT")
    if not (when_html and target_html and effect_html):
        return None

    when_text = _strip_html(when_html).lower()
    if not re.search(r"(just\s+)?after an enemy unit has selected its targets", when_text):
        return None
    phases: set[str] = set()
    if "shooting phase" in when_text:
        phases.add("shooting")
    if "fight phase" in when_text:
        phases.add("fight")
    if not phases:
        return None

    target_text = _strip_html(target_html)
    target_keywords = _extract_kwb_keywords(target_html)
    if not target_keywords:
        try:
            m = re.search(r"\bone\s+(.+?)\s+unit from your army", target_text, flags=re.IGNORECASE)
        except Exception:
            raise
        if m:
            kw_text = m.group(1).strip()
            if kw_text:
                target_keywords = [
                    part.strip()
                    for part in re.split(r"\s+or\s+|\s+and\s+", kw_text, flags=re.IGNORECASE)
                    if part.strip()
                ]
    replaced = target_text
    for kw in sorted(target_keywords, key=len, reverse=True):
        if kw:
            replaced = re.sub(re.escape(kw), "KW", replaced, flags=re.IGNORECASE)
    replaced_norm = _normalize_token(replaced)
    mode = "all"
    if re.search(r"\bkw\b\s+or\s+kw\b", replaced_norm):
        mode = "any"
    replaced_norm = re.sub(r"\bkw\b(\s+kw\b)+", "kw", replaced_norm)
    replaced_norm = re.sub(r"\bkw\b(\s+(or|and)\s+kw\b)+", "kw", replaced_norm)
    canonical_kw = _normalize_token(
        "one kw unit from your army that was selected as the target of one or more of the attacking unit's attacks"
    )
    canonical_plain = _normalize_token(
        "one unit from your army that was selected as the target of one or more of the attacking unit's attacks"
    )
    if ("kw" in replaced_norm and replaced_norm != canonical_kw) or (
        "kw" not in replaced_norm and replaced_norm != canonical_plain
    ):
        return None

    effect_text = _strip_html(effect_html).lower().strip().rstrip(".")
    if any(word in effect_text for word in (" if ", " unless ", " while ", " instead ", " in addition", " then ")):
        return None

    duration = None
    rest = None
    for label, prefix in (
        ("phase", "until the end of the phase,"),
        ("attacker", "until the attacking unit has finished making its attacks,"),
    ):
        if effect_text.startswith(prefix):
            duration = label
            rest = effect_text[len(prefix) :].strip()
            break
    if duration is None or rest is None:
        return None

    hit_re = re.compile(
        r"each time (an|a) (?:(?P<atype>melee|ranged) )?attack targets your unit, subtract 1 from the hit roll"
    )
    wound_re = re.compile(
        r"each time (an|a) (?:(?P<atype>melee|ranged) )?attack targets your unit, subtract 1 from the wound roll"
    )
    ap_re = re.compile(
        r"each time an attack targets your unit, worsen the armour penetration characteristic of that attack by 1"
    )
    damage_re = re.compile(
        r"each time (an|a) (?:(?P<atype>melee|ranged) )?attack is allocated to a model in your unit, subtract 1 from the damage characteristic of that attack"
    )
    invuln_re = re.compile(
        r"(all )?models in your unit have a (?P<value>\d)\+ invulnerable save"
    )
    invuln_unit_re = re.compile(r"your unit has a (?P<value>\d)\+ invulnerable save")
    fnp_re = re.compile(
        r"(all )?models in your unit have the feel no pain (?P<value>\d)\+ ability"
    )
    fnp_unit_re = re.compile(r"your unit has the feel no pain (?P<value>\d)\+ ability")

    m = hit_re.fullmatch(rest)
    if m:
        return {
            "name": name or "",
            "phases": phases,
            "duration": duration,
            "effect_type": "hit_penalty",
            "value": 1,
            "attack_type": (m.group("atype") or "any"),
            "target_keywords": list(target_keywords or []),
            "target_keyword_mode": mode,
        }
    m = wound_re.fullmatch(rest)
    if m:
        return {
            "name": name or "",
            "phases": phases,
            "duration": duration,
            "effect_type": "wound_penalty",
            "value": 1,
            "attack_type": (m.group("atype") or "any"),
            "target_keywords": list(target_keywords or []),
            "target_keyword_mode": mode,
        }
    if ap_re.fullmatch(rest):
        return {
            "name": name or "",
            "phases": phases,
            "duration": duration,
            "effect_type": "ap_worsen",
            "value": 1,
            "attack_type": "any",
            "target_keywords": list(target_keywords or []),
            "target_keyword_mode": mode,
        }
    m = damage_re.fullmatch(rest)
    if m:
        return {
            "name": name or "",
            "phases": phases,
            "duration": duration,
            "effect_type": "damage_reduction",
            "value": 1,
            "attack_type": (m.group("atype") or "any"),
            "target_keywords": list(target_keywords or []),
            "target_keyword_mode": mode,
        }
    m = invuln_re.fullmatch(rest) or invuln_unit_re.fullmatch(rest)
    if m:
        return {
            "name": name or "",
            "phases": phases,
            "duration": duration,
            "effect_type": "invulnerable_save",
            "value": int(m.group("value")),
            "attack_type": "any",
            "target_keywords": list(target_keywords or []),
            "target_keyword_mode": mode,
        }
    m = fnp_re.fullmatch(rest) or fnp_unit_re.fullmatch(rest)
    if m:
        return {
            "name": name or "",
            "phases": phases,
            "duration": duration,
            "effect_type": "feel_no_pain",
            "value": int(m.group("value")),
            "attack_type": "any",
            "target_keywords": list(target_keywords or []),
            "target_keyword_mode": mode,
        }

    return None


def parse_charge_melee_ap_stratagem(name: str, description: str) -> Optional[Dict[str, Any]]:
    """
    Parse stratagems that grant +AP to melee weapons for a unit that charged and has not fought yet.

    Pattern (strict):
    - WHEN: Fight phase
    - TARGET: unit that made a Charge move this turn and has not been selected to fight this phase
    - EFFECT: improve the Armour Penetration characteristic of melee weapons equipped by models in your unit by X
    """
    if not description:
        return None

    when_html = _extract_stratagem_section(description, "WHEN")
    target_html = _extract_stratagem_section(description, "TARGET")
    effect_html = _extract_stratagem_section(description, "EFFECT")
    if not (when_html and target_html and effect_html):
        return None

    when_text = _strip_html(when_html).lower()
    if "fight phase" not in when_text:
        return None

    target_text = _strip_html(target_html).lower()
    if "charge move" not in target_text or "this turn" not in target_text:
        return None
    if not re.search(r"not\s+been\s+selected\s+to\s+fight\s+this\s+phase", target_text):
        return None

    effect_text = _strip_html(effect_html).lower()
    m = re.search(
        r"improve\s+the\s+armour\s+penetration\s+characteristic\s+of\s+melee\s+weapons\s+equipped\s+"
        r"by\s+models\s+in\s+(your|that)\s+unit\s+by\s+(\d+)",
        effect_text,
    )
    if not m:
        return None

    keywords = _extract_kwb_keywords(target_html)
    return {
        "ap_bonus": int(m.group(2)),
        "phases": ["fight"],
        "requires_charge": True,
        "requires_not_fought": True,
        "target_keywords": keywords,
        "target_keyword_mode": "all",
        "name": name or "",
    }


def parse_consolidate_move_stratagem(name: str, description: str) -> Optional[Dict[str, Any]]:
    """
    Parse stratagems that extend Consolidation moves within the Fight phase.

    Pattern (strict):
    - WHEN: Fight phase, just before a unit Consolidates
    - TARGET: that unit
    - EFFECT: each time a model consolidates, it can move up to X" instead of up to 3"
      Optional: provided the unit ends that Consolidation move within Engagement Range of one or more enemy units
    """
    if not description:
        return None

    when_html = _extract_stratagem_section(description, "WHEN")
    target_html = _extract_stratagem_section(description, "TARGET")
    effect_html = _extract_stratagem_section(description, "EFFECT")
    if not (when_html and target_html and effect_html):
        return None

    when_text = _strip_html(when_html).lower()
    if "fight phase" not in when_text:
        return None
    if "just before" not in when_text or "consolidat" not in when_text:
        return None

    effect_text = _strip_html(effect_html).lower().strip().rstrip(".")
    prefix = "until the end of the phase,"
    if not effect_text.startswith(prefix):
        return None
    rest = effect_text[len(prefix) :].strip()

    m = re.match(
        r"each time a model in (your|that) unit makes a consolidation move, "
        r"it can move up to (\d+)\" instead of up to (\d+)\"",
        rest,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    try:
        max_dist = int(m.group(2))
    except Exception:
        raise
    tail = rest[m.end() :].strip().rstrip(".")
    if tail.startswith(","):
        tail = tail[1:].strip()
    requires_engagement = False
    if tail:
        if re.fullmatch(
            r"provided your unit ends that consolidation move within engagement range of one or more enemy units",
            tail,
        ):
            requires_engagement = True
        else:
            return None

    keywords = _extract_kwb_keywords(target_html)
    return {
        "max_distance": max_dist,
        "requires_engagement": requires_engagement,
        "phases": ["fight"],
        "target_keywords": keywords,
        "target_keyword_mode": "all",
        "name": name or "",
    }


def defensive_reaction_note(spec: Dict[str, Any]) -> str:
    if not spec:
        return "Generic defensive reaction."
    effect_type = spec.get("effect_type")
    value = spec.get("value")
    attack_type = (spec.get("attack_type") or "any").strip().lower()
    duration = spec.get("duration", "")

    effect_desc = "defensive effect"
    if effect_type == "hit_penalty":
        effect_desc = f"-{int(value or 1)} to hit"
    elif effect_type == "wound_penalty":
        effect_desc = f"-{int(value or 1)} to wound"
    elif effect_type == "ap_worsen":
        effect_desc = f"worsen AP by {int(value or 1)}"
    elif effect_type == "damage_reduction":
        effect_desc = f"-{int(value or 1)} Damage"
    elif effect_type == "invulnerable_save":
        effect_desc = f"{int(value)}+ invulnerable save"
    elif effect_type == "feel_no_pain":
        effect_desc = f"Feel No Pain {int(value)}+"

    if attack_type in ("melee", "ranged"):
        effect_desc = f"{effect_desc} ({attack_type})"

    duration_desc = "until end of phase"
    if duration == "attacker":
        duration_desc = "until the attacking unit finishes its attacks"

    keywords = spec.get("target_keywords") or []
    if keywords:
        joiner = " or " if spec.get("target_keyword_mode") == "any" else " "
        target_desc = f"{joiner.join(keywords)} unit"
    else:
        target_desc = "unit"
    return f"Defensive reaction after targets selected: {target_desc} gains {effect_desc} {duration_desc}."


class Stratagem:
    def __init__(
        self,
        *,
        id: str,
        name: str,
        type: str,
        description: str,
        cp_cost: int,
        turn: str,
        phase: str,
        detachment: str,
        faction_id: str,
        effect: Optional[Callable] = None,
        conditions: Optional[Callable] = None,
    ) -> None:
        self.id = id
        self.name = name
        self.type = type
        self.description = description
        self.cp_cost = int(cp_cost) if isinstance(cp_cost, (int, str)) else 0
        self.turn = turn
        self.phase = phase
        self.detachment = detachment or ""
        self.faction_id = faction_id or ""
        self.effect = effect
        self.conditions = conditions

    @staticmethod
    def from_json(data: Dict[str, Any]) -> "Stratagem":
        return Stratagem(
            id=data.get("id", ""),
            name=data.get("name", ""),
            type=data.get("type", ""),
            description=data.get("description", ""),
            cp_cost=data.get("cp_cost", 0),
            turn=data.get("turn", ""),
            phase=data.get("phase", ""),
            detachment=data.get("detachment", ""),
            faction_id=data.get("faction_id", ""),
        )

    def applies_to_army(self, army) -> bool:
        # Global if no faction_id
        is_global = self.faction_id == ""
        if is_global:
            return True
        # Otherwise must match faction and (if present) detachment
        if getattr(army, "faction_id", None) and army.faction_id != self.faction_id:
            return False
        if self.detachment:
            mgr = None
            get_mgr = getattr(army, "get_detachment_manager_for_faction", None)
            if callable(get_mgr):
                mgr = get_mgr(self.faction_id)
            if mgr is not None:
                return bool(mgr.detachment_matches(self.detachment))
            # Must match detachment name exactly (source data string)
            return getattr(army, "detachment_type", "") == self.detachment
        return True

    def can_use(self, player, game, **kwargs) -> bool:
        # Targeting restrictions:
        # - Embarked units cannot be targeted by stratagems (no exceptions here).
        # - Battle-shocked units cannot be targeted by stratagems, except INSANE BRAVERY.
        tgt = _extract_friendly_target_unit_from_kwargs(kwargs)
        # Embarked is always blocked (rule is broader than Battle-shock).
        if _unit_cannot_be_target_of_stratagem(tgt):
            if (self.name or "").strip().upper() == "INSANE BRAVERY":
                # Allow INSANE BRAVERY only to bypass Battle-shock restriction, not embarked restriction.
                # If target is embarked, still blocked.
                if bool(getattr(tgt, "is_embarked", False)):
                    return False
                if getattr(tgt, "embarked_in", None) is not None:
                    return False
                # Otherwise, if this was blocked only due to battle-shock, allow it.
                # (We can't perfectly distinguish reasons here, so do a focused check.)
                is_bs = getattr(tgt, "is_battle_shocked", None)
                if callable(is_bs) and bool(is_bs()):
                    pass
                else:
                    # If not battle-shocked but still blocked, keep blocked.
                    return False
            else:
                return False

        # Allow CP cost modifiers (e.g. Direct the Slaughter) to affect affordability.
        target_unit = kwargs.get("target_unit", None)
        eff_cost = self.cp_cost
        preview_fn = getattr(player, "preview_stratagem_cp_cost", None)
        if callable(preview_fn):
            preview = preview_fn(self, target_unit=target_unit) or {}
            eff_cost = int(preview.get("cost", self.cp_cost))
        if player.command_points < eff_cost:
            return False
        # Phase awareness
        phase_name = kwargs.get("phase_name")
        if phase_name and not self.is_phase_allowed(phase_name):
            return False
        # Turn awareness
        active_player = getattr(game, 'get_current_player', lambda: None)()
        is_active_turn = active_player is player
        if not self.is_turn_allowed(is_active_turn):
            return False
        if self.conditions is None:
            return True
        return bool(self.conditions(player, game, **kwargs))

    def use(self, player, game, **kwargs) -> bool:
        if not self.can_use(player, game, **kwargs):
            return False
        # Apply CP cost modifiers now (consumes once-per-battle-round discounts if used)
        target_unit = kwargs.get("target_unit", None)
        eff_cost = self.cp_cost
        apply_fn = getattr(player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(self, target_unit=target_unit) or {}
            eff_cost = int(preview.get("cost", self.cp_cost))
        if not player.spend_command_points(eff_cost, reason=f"Stratagem: {self.name}", source="stratagem"):
            return False
        # Drukhari: allow optional Pain token spends for stratagem add-on effects.
        get_army = getattr(player, "get_army", None)
        army = get_army() if callable(get_army) else None
        mgr = getattr(army, "power_from_pain", None) if army is not None else None
        if mgr is not None:
            cost = int(mgr.stratagem_pain_token_cost(self) or 0)
            if cost > 0 and int(getattr(mgr, "tokens", 0) or 0) >= cost:
                ctx = {
                    "ability_name": "Power from Pain",
                    "stratagem": getattr(self, "name", None) or "",
                    "pain_cost": cost,
                }
                should_fn = getattr(player, "_should_use_optional_ability", None)
                should = bool(should_fn("POWER_FROM_PAIN_STRATAGEM", ctx)) if callable(should_fn) else False
                if should and mgr.spend_pain_for_stratagem(self):
                    kwargs["pain_tokens_spent"] = cost
        if self.effect is not None:
            self.effect(player, game, **kwargs)
        else:
            print(f"INFO: No effect implemented for Stratagem: {self.name}")
        return True

    def __str__(self) -> str:
        return f"{self.name} ({self.type}): {self.description}"

    def __repr__(self) -> str:
        return (
            f"Stratagem(id={self.id}, name={self.name}, type={self.type}, cp_cost={self.cp_cost}, "
            f"turn={self.turn}, phase={self.phase}, detachment={self.detachment}, faction_id={self.faction_id})"
        )

    # ---------------- Timing helpers ----------------
    def is_phase_allowed(self, phase_name: str) -> bool:
        """
        phase_name: canonical current phase name, e.g. 'Command phase', 'Movement phase', 'Shooting phase', 'Charge phase', 'Fight phase'.
        Source data may contain 'Any phase' or combined text like 'Shooting or Fight phase'.
        """
        if not phase_name:
            return True
        current = phase_name.strip().lower()
        raw = (self.phase or "").strip().lower()
        if not raw or 'any phase' in raw:
            return True
        # Allow simple substring or 'x or y' checks
        if current in raw:
            return True
        # Common aliasing
        aliases = {
            'command phase': ['command'],
            'movement phase': ['movement', 'move'],
            'shooting phase': ['shooting', 'shoot'],
            'charge phase': ['charge'],
            'fight phase': ['fight', 'fighting']
        }
        for canonical, keys in aliases.items():
            if current == canonical:
                if any(k in raw for k in keys):
                    return True
        return False

    def is_turn_allowed(self, is_active_turn: bool) -> bool:
        raw = (self.turn or "").strip().lower()
        if not raw or 'either' in raw:
            return True
        if 'your turn' in raw:
            return is_active_turn
        if "opponent's turn" in raw or 'opponents turn' in raw:
            return not is_active_turn
        return True


class StratagemManager:
    def __init__(self, player) -> None:
        # Lazy import to avoid cycles
        from warhammer40k_ai.waha_helper import WahaHelper

        self.player = player
        self.game = getattr(player, "game", None)
        self._waha = WahaHelper()
        self.available: List[Stratagem] = []
        self._subscriptions_enabled = False
        self._event_group: Optional[str] = None
        self._subscribed_handlers: Dict[tuple[str, str], Callable] = {}
        self._required_events: set[str] = set()
        self._last_failed_battle_shock_unit = None
        self._current_phase_name: Optional[str] = None
        self._pending_reactions: List[Dict[str, Any]] = []
        self._reaction_timeout_s = 5.0
        # Track temporary per-phase stratagem buffs that must be cleaned up.
        self._epic_challenge_models: list[Any] = []
        # Fight-phase kill flags for "A WORTHY SKULL".
        self._worthy_skull_kills: Dict[Any, bool] = {}
        # Emperor's Children: track units that destroyed enemies in their Fight phase.
        self._ec_units_destroyed_enemy_in_fight: set[str] = set()
        # Cache parsed generic defensive reaction specs by stratagem id/name.
        self._defensive_reaction_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        # Cache parsed generic charge-based melee AP stratagem specs by stratagem id/name.
        self._charge_melee_ap_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        # Cache parsed consolidate move stratagem specs by stratagem id/name.
        self._consolidate_move_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        # Track recent shooting targets per attacker (for post-shooting reactions).
        self._recent_shooting_targets: Dict[str, List[Any]] = {}
        self.refresh_available()
        # Per-turn usage limits (e.g., Overwatch once/turn)
        self._used_this_turn: Dict[str, bool] = {
            'OVERWATCH': False,
        }
        # Core rules: a player cannot use the same Stratagem more than once in the same phase.
        # (Unless an ability explicitly names the Stratagem; we do not implement such bypasses generically.)
        self._used_stratagems_this_phase: set[str] = set()
        # Track Heroic Intervention targets per phase for named exceptions.
        self._heroic_intervention_units_this_phase: set[str] = set()
        # Once-per-battle limits (e.g., INSANE BRAVERY once per battle)
        self._used_once_per_battle: Dict[str, bool] = {
            'INSANE BRAVERY': False,
        }
        # Once-per-battle-round limits (e.g., SUMMONED BY SLAUGHTER)
        self._used_battle_round: Dict[str, int] = {}
        # Lions of the Emperor: Gilded Champion cannot target the same model twice per battle.
        self._gilded_champion_used_models: set[str] = set()

    def refresh_available(self) -> None:
        """Refresh stratagem list and subscriptions after army changes."""
        try:
            self.game = getattr(self.player, "game", None)
        except Exception:
            raise
        if not isinstance(getattr(self, "_gilded_champion_used_models", None), set):
            self._gilded_champion_used_models = set(getattr(self, "_gilded_champion_used_models", []) or [])
        try:
            self._defensive_reaction_cache.clear()
            self._charge_melee_ap_cache.clear()
            self._consolidate_move_cache.clear()
        except Exception:
            raise
        self._build_available()
        if self._subscriptions_enabled:
            self._unsubscribe_events()
            self._subscribe_events()

    def enable_event_subscriptions(self, *, event_system=None, group: Optional[str] = None) -> None:
        if group:
            self._event_group = group
        self._subscriptions_enabled = True
        self._subscribe_events(event_system=event_system, group=self._event_group)

    def disable_event_subscriptions(self, *, event_system=None, group: Optional[str] = None) -> None:
        if group:
            self._event_group = group
        self._unsubscribe_events(event_system=event_system, group=self._event_group)
        self._subscriptions_enabled = False

    @staticmethod
    def _normalize_stratagem_name(name: str) -> str:
        text = str(name or "")
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = text.replace("\u2013", "-").replace("\u2014", "-")
        text = text.replace("\u00e2\u20ac\u2122", "'")
        text = text.replace("\u0192?T", "'")
        return text.strip().upper()

    def _available_name_set(self) -> set[str]:
        names: set[str] = set()
        for s in list(self.available or []):
            name = self._normalize_stratagem_name(getattr(s, "name", "") or "")
            if name:
                names.add(name)
        return names

    def _compute_required_handlers(self) -> Dict[str, List[Callable]]:
        handlers: Dict[str, List[Callable]] = {}
        names = self._available_name_set()
        if not names:
            return handlers

        def add(event_name: str, handler: Callable) -> None:
            handlers.setdefault(event_name, []).append(handler)

        # Always track phase to reset per-phase usage and phase-aware reactions.
        add("phase_start", self._on_phase_start)

        if "GILDED CHAMPION" in names:
            add("once_per_battle_ability_used", self._on_once_per_battle_ability_used)

        if "COMMAND RE-ROLL" in names:
            add("roll_made", self._on_roll_made)

        if "INSANE BRAVERY" in names:
            add("battle_shock_test_started", self._on_battle_shock_test_started)
            add("battle_shock_test_resolved", self._on_battle_shock_test_resolved)

        if "BERZERKER'S WRATH" in names:
            add("blood_surge_triggered", self._on_blood_surge_triggered)

        if "COUNTER-OFFENSIVE" in names:
            add("fight_sequence_complete", self._on_fight_sequence_complete)

        if "EPIC CHALLENGE" in names:
            add("fight_unit_selected", self._on_fight_unit_selected)

        if names & {"OVERWATCH", "FIRE OVERWATCH", "APOPLECTIC FRENZY"}:
            add("unit_move_started", self._on_unit_move_started)

        if names & {"OVERWATCH", "FIRE OVERWATCH", "TANK SHOCK", "HEROIC INTERVENTION", "FEIGNED RETREAT", "CUT DOWN THE WEAK"}:
            add("unit_move_ended", self._on_unit_move_ended)

        if names & {"A GRIM WARNING", "BLOOD OFFERING", "UNBOUND ARROGANCE", "TERRIFYING SPECTACLE"}:
            add("unit_destroyed", self._on_unit_destroyed)

        if "SKULLS FOR THE SKULL THRONE!" in names:
            add("model_destroyed", self._on_model_destroyed)

        if "SUMMONED BY SLAUGHTER" in names:
            add("model_destroyed_before_removal", self._on_model_destroyed_before_removal)

        if "FIRE AND FADE" in names:
            add("unit_shooting_resolved", self._on_unit_shooting_resolved_fire_and_fade)
        if "REACTIVE REPOSITION" in names:
            add("unit_shooting_resolved", self._on_unit_shooting_resolved_reactive_reposition)

        has_consolidate_spec = False
        has_charge_melee_ap_spec = False
        defensive_phases: set[str] = set()
        defensive_attacker_phases: set[str] = set()
        defensive_duration_phase = False
        for s in list(self.available or []):
            try:
                spec = self._get_defensive_reaction_spec(s)
            except Exception:
                raise
            if spec:
                phases = set(spec.get("phases") or [])
                defensive_phases.update(phases)
                duration = str(spec.get("duration") or "").strip().lower()
                if duration == "attacker":
                    defensive_attacker_phases.update(phases)
                if duration == "phase":
                    defensive_duration_phase = True
            if not has_consolidate_spec:
                try:
                    has_consolidate_spec = bool(self._get_consolidate_move_spec(s))
                except Exception:
                    raise
            if not has_charge_melee_ap_spec:
                try:
                    has_charge_melee_ap_spec = bool(self._get_charge_melee_ap_spec(s))
                except Exception:
                    raise
        shooting_reaction_names = {
            "GO TO GROUND",
            "SMOKESCREEN",
            "ARMOUR OF CONTEMPT",
            "THE FOE FORESEEN",
            "BLESSING OF BURNING BLOOD",
            "LIGHTNING-FAST REACTIONS",
            "UNYIELDING FORMS",
        }
        fight_reaction_names = {
            "DEATHLESS DUTY",
            "DEATH ECSTASY",
            "FRENZIED RESILIENCE",
            "ARMOUR OF CONTEMPT",
            "THE FOE FORESEEN",
            "BLESSING OF BURNING BLOOD",
            "LIGHTNING-FAST REACTIONS",
            "UNYIELDING FORMS",
        }

        has_generic_defensive_shooting = "shooting" in defensive_phases
        has_generic_defensive_fight = "fight" in defensive_phases

        if (names & shooting_reaction_names) or has_generic_defensive_shooting:
            add("shooting_targets_selected", self._on_shooting_targets_selected)

        if (names & fight_reaction_names) or has_generic_defensive_fight:
            add("fight_targets_selected", self._on_fight_targets_selected)

        needs_attacker_cleanup_shooting = (
            "ARMOUR OF CONTEMPT" in names
            or "THE FOE FORESEEN" in names
            or ("shooting" in defensive_attacker_phases)
        )
        needs_attacker_cleanup_fight = (
            "ARMOUR OF CONTEMPT" in names
            or "THE FOE FORESEEN" in names
            or ("fight" in defensive_attacker_phases)
        )

        if needs_attacker_cleanup_shooting:
            add("unit_shooting_resolved", self._on_unit_shooting_resolved_armour_of_contempt_cleanup)

        if "A WORTHY SKULL" in names:
            add("fight_attacks_resolved", self._on_fight_attacks_resolved)

        if has_consolidate_spec:
            add("fight_attacks_resolved", self._on_fight_attacks_resolved_consolidate_stratagems)

        if needs_attacker_cleanup_fight:
            add("fight_attacks_resolved", self._on_fight_attacks_resolved_armour_of_contempt_cleanup)

        phase_end_trigger_names = {
            "MURDER-CALL",
            "NEW ORDERS",
            "RAPID INGRESS",
            "SKYBORNE SANCTUARY",
            "WEBWAY TUNNEL",
            "ENDLESS SERVITUDE",
        }
        phase_end_cleanup_names = {
            "GO TO GROUND",
            "SMOKESCREEN",
            "BLITZING FIREPOWER",
            "LIGHTNING-FAST REACTIONS",
            "DAEMONIC FURY",
            "HACK AND SLASH",
            "FRENZIED RESILIENCE",
            "UNYIELDING FORMS",
            "MERCILESS RECLAMATION",
            "DIMENSIONAL TUNNEL",
            "CHRONOSHIFT",
        }
        needs_phase_end = bool(
            (names & phase_end_trigger_names)
            or (names & phase_end_cleanup_names)
            or defensive_duration_phase
            or has_charge_melee_ap_spec
            or has_consolidate_spec
        )
        if needs_phase_end:
            add("phase_end", self._on_phase_end)

        return handlers

    def _dequeue_reaction_by_name(self, stratagem_name: str) -> None:
        """Remove the first pending reaction matching this stratagem name."""
        try:
            target = (stratagem_name or "").strip().lower()
            if not target:
                return
            for i, r in enumerate(list(self._pending_reactions)):
                if str(r.get("stratagem", "")).strip().lower() == target:
                    self._pending_reactions.pop(i)
                    return
        except Exception:
            raise
    def _now(self) -> float:
        return float(time.monotonic())

    def _attacker_unit_key(self, unit: Any) -> Optional[str]:
        if unit is None:
            return None
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            raise
        return get_entity_id(root)
    @staticmethod
    def _phase_key_from_name(phase_name: str) -> str:
        return str(phase_name or "").strip().upper().replace(" ", "_")

    def _get_defensive_reaction_spec(self, stratagem: Stratagem) -> Optional[Dict[str, Any]]:
        if stratagem is None:
            return None
        name_u = (str(getattr(stratagem, "name", "") or "")).strip().upper()
        if name_u in IMPLEMENTED_STRATAGEM_NAMES:
            return None
        key = str(getattr(stratagem, "id", "") or name_u)
        if key in self._defensive_reaction_cache:
            return self._defensive_reaction_cache[key]
        spec = parse_defensive_reaction_stratagem(stratagem.name or "", stratagem.description or "")
        self._defensive_reaction_cache[key] = spec
        return spec

    def _get_charge_melee_ap_spec(self, stratagem: Stratagem) -> Optional[Dict[str, Any]]:
        if stratagem is None:
            return None
        name_u = (str(getattr(stratagem, "name", "") or "")).strip().upper()
        if name_u in IMPLEMENTED_STRATAGEM_NAMES:
            return None
        key = str(getattr(stratagem, "id", "") or name_u)
        if key in self._charge_melee_ap_cache:
            return self._charge_melee_ap_cache[key]
        spec = parse_charge_melee_ap_stratagem(stratagem.name or "", stratagem.description or "")
        self._charge_melee_ap_cache[key] = spec
        return spec

    def _get_consolidate_move_spec(self, stratagem: Stratagem) -> Optional[Dict[str, Any]]:
        if stratagem is None:
            return None
        name_u = (str(getattr(stratagem, "name", "") or "")).strip().upper()
        if name_u in IMPLEMENTED_STRATAGEM_NAMES:
            return None
        key = str(getattr(stratagem, "id", "") or name_u)
        if key in self._consolidate_move_cache:
            return self._consolidate_move_cache[key]
        spec = parse_consolidate_move_stratagem(stratagem.name or "", stratagem.description or "")
        self._consolidate_move_cache[key] = spec
        return spec

    def _unit_matches_defensive_target_spec(self, unit: Any, spec: Dict[str, Any]) -> bool:
        if unit is None or spec is None:
            return False
        keywords = list(spec.get("target_keywords") or [])
        if not keywords:
            return True
        mode = str(spec.get("target_keyword_mode") or "all").strip().lower()

        def _match_keyword(kw: str) -> bool:
            if not kw:
                return False
            try:
                if unit.has_any_keyword(kw):
                    return True
            except Exception:
                raise
            if " " in kw:
                parts = [p for p in kw.split(" ") if p]
                if parts:
                    try:
                        return all(unit.has_any_keyword(p) for p in parts)
                    except Exception:
                        raise
            return False

        if mode == "any":
            return any(_match_keyword(k) for k in keywords)
        return all(_match_keyword(k) for k in keywords)

    def _consolidate_requires_engagement_possible(self, unit: Any, max_distance: float) -> bool:
        if unit is None:
            return False
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return True
        try:
            enemy_units = list(game_map.get_enemy_units(unit) or [])
        except Exception:
            try:
                enemy_units = [u for u in list(getattr(game_map, "units", []) or []) if u is not None and getattr(u, "faction", None) != getattr(unit, "faction", None)]
            except Exception:
                enemy_units = []
        if not enemy_units:
            return False
        try:
            from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL
        except Exception:
            ENGAGEMENT_RANGE_HORIZONTAL = 1.0
        try:
            for enemy in enemy_units:
                if enemy is None:
                    continue
                if not getattr(enemy, "is_alive", lambda: True)():
                    continue
                if getattr(enemy, "deployed", True) is False:
                    continue
                if hasattr(game_map, "is_within_engagement_range") and game_map.is_within_engagement_range(unit, enemy):
                    return True
        except Exception:
            pass
        min_dist = None
        for enemy in enemy_units:
            try:
                if enemy is None or not enemy.is_alive():
                    continue
            except Exception:
                continue
            try:
                dist = float(game_map.get_distance_between_units(unit, enemy))
            except Exception:
                continue
            if min_dist is None or dist < min_dist:
                min_dist = dist
        if min_dist is None:
            return False
        return float(min_dist) <= float(max_distance or 0) + float(ENGAGEMENT_RANGE_HORIZONTAL or 1.0)

    def _record_ec_last_turn_flags(self) -> None:
        try:
            army = self.player.get_army()
        except Exception:
            army = None
        mgr = getattr(army, "emperors_children", None) if army is not None else None
        if mgr is None or not getattr(mgr, "is_peerless_bladesmen", lambda: False)():
            self._ec_units_destroyed_enemy_in_fight.clear()
            return
        seen = set()
        for unit in list(getattr(army, "units", []) or []):
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            rid = get_entity_id(root)
            if rid in seen:
                continue
            seen.add(rid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            try:
                charged_owner = str(getattr(getattr(root, "round_state", None), "charged_turn_owner", "") or "")
                sr["ec_last_turn_charged"] = bool(
                    getattr(getattr(root, "round_state", None), "charged_this_round", False)
                    and charged_owner
                    and charged_owner == str(getattr(self.player, "id", "") or "")
                )
            except Exception:
                sr["ec_last_turn_charged"] = False
            sr["ec_last_turn_destroyed_enemy_in_fight"] = rid in self._ec_units_destroyed_enemy_in_fight
            root.special_rules = sr
        self._ec_units_destroyed_enemy_in_fight.clear()

    def _append_defensive_effect(self, unit: Any, key: str, entry: Dict[str, Any]) -> None:
        try:
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            items = sr.get(key)
            if not isinstance(items, list):
                items = []
            items.append(dict(entry))
            sr[key] = items
            unit.special_rules = sr
        except Exception:
            raise
    def _apply_generic_defensive_effect(
        self,
        unit: Any,
        spec: Dict[str, Any],
        *,
        attacker_unit: Any,
        phase_name: str,
        source_name: str,
    ) -> bool:
        if unit is None or spec is None:
            return False
        duration = spec.get("duration")
        effect_type = spec.get("effect_type")
        value = int(spec.get("value") or 0)
        attack_type = str(spec.get("attack_type") or "any").strip().lower()
        attacker_key = self._attacker_unit_key(attacker_unit) if duration == "attacker" else None
        expires_phase = self._phase_key_from_name(phase_name) if duration == "phase" else None
        entry = {
            "value": value,
            "attack_type": attack_type,
            "attacker_key": attacker_key,
            "expires_phase": expires_phase,
            "source": str(source_name or "Stratagem"),
        }

        if effect_type == "ap_worsen":
            if duration == "phase":
                self._append_defensive_effect(unit, "defensive_ap_worsen_phase", entry)
                return True
            if attacker_unit is None:
                return False
            return bool(self._apply_armour_of_contempt(unit, attacker_unit, amount=value))
        if effect_type == "hit_penalty":
            self._append_defensive_effect(unit, "defensive_hit_mods", entry)
            return True
        if effect_type == "wound_penalty":
            self._append_defensive_effect(unit, "defensive_wound_mods", entry)
            return True
        if effect_type == "damage_reduction":
            self._append_defensive_effect(unit, "defensive_damage_reductions", entry)
            return True
        if effect_type == "invulnerable_save":
            self._append_defensive_effect(unit, "defensive_invuln_overrides", entry)
            return True
        if effect_type == "feel_no_pain":
            self._append_defensive_effect(unit, "defensive_fnp_overrides", entry)
            return True
        return False

    def _clear_defensive_effects_for_attacker(self, attacker_unit: Any) -> None:
        key = self._attacker_unit_key(attacker_unit)
        if key is None:
            return
        try:
            units = list(getattr(self.player.get_army(), "units", []) or [])
        except Exception:
            raise
        for unit in units:
            try:
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                for k in (
                    "defensive_hit_mods",
                    "defensive_wound_mods",
                    "defensive_damage_reductions",
                    "defensive_invuln_overrides",
                    "defensive_fnp_overrides",
                    "defensive_ap_worsen_phase",
                ):
                    items = sr.get(k)
                    if not isinstance(items, list):
                        continue
                    kept = [e for e in items if str(e.get("attacker_key", "")) != str(key)]
                    if kept:
                        sr[k] = kept
                    else:
                        sr.pop(k, None)
                unit.special_rules = sr
            except Exception:
                raise
    def _clear_defensive_effects_for_phase(self, phase_name: str) -> None:
        phase_key = self._phase_key_from_name(phase_name)
        if not phase_key:
            return
        try:
            units = list(getattr(self.player.get_army(), "units", []) or [])
        except Exception:
            raise
        for unit in units:
            try:
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                for k in (
                    "defensive_hit_mods",
                    "defensive_wound_mods",
                    "defensive_damage_reductions",
                    "defensive_invuln_overrides",
                    "defensive_fnp_overrides",
                ):
                    items = sr.get(k)
                    if not isinstance(items, list):
                        continue
                    kept = [e for e in items if str(e.get("expires_phase", "")) != str(phase_key)]
                    if kept:
                        sr[k] = kept
                    else:
                        sr.pop(k, None)
                unit.special_rules = sr
            except Exception:
                raise
    def _queue_generic_defensive_reactions(
        self,
        attacking_unit: Any,
        target_units: Optional[List[Any]],
        *,
        phase_name: str,
    ) -> None:
        if attacking_unit is None:
            return
        phase_key = str(phase_name or "").strip().lower()
        phase_tag = None
        if "shooting" in phase_key:
            phase_tag = "shooting"
        elif "fight" in phase_key:
            phase_tag = "fight"
        if phase_tag is None:
            return
        for s in list(self.available or []):
            spec = self._get_defensive_reaction_spec(s)
            if not spec:
                continue
            if phase_tag not in set(spec.get("phases") or []):
                continue
            if self.player.command_points < int(getattr(s, "cp_cost", 0) or 0):
                continue
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                continue
            candidates = []
            for u in list(target_units or []):
                try:
                    if u is None or not u.is_alive():
                        continue
                    if u.get_parent_army().player is not self.player:
                        continue
                    if _unit_cannot_be_target_of_stratagem(u):
                        continue
                    if not self._unit_matches_defensive_target_spec(u, spec):
                        continue
                    candidates.append(u)
                except Exception:
                    raise
            if not candidates:
                continue
            already = False
            for r in self._pending_reactions:
                try:
                    if (
                        r.get("event") in ("shooting_targets_selected", "fight_targets_selected")
                        and r.get("stratagem") == s.name
                        and r.get("attacking_unit") is attacking_unit
                    ):
                        already = True
                        break
                except Exception:
                    raise
            if already:
                continue
            payload = {
                "event": "shooting_targets_selected" if phase_tag == "shooting" else "fight_targets_selected",
                "phase_name": phase_name,
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "attacking_unit": attacking_unit,
                "target_units": list(target_units or []),
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload)

    def _apply_armour_of_contempt(self, target_unit: Any, attacker_unit: Any, *, amount: int = 1) -> bool:
        if target_unit is None or attacker_unit is None:
            return False
        try:
            root = target_unit.get_attached_unit_root()
        except Exception:
            raise
        key = self._attacker_unit_key(attacker_unit)
        if key is None:
            return False
        try:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            spec = sr.get("armour_of_contempt_ap_worsen")
            if not isinstance(spec, dict):
                spec = {}
            spec[str(key)] = int(amount)
            sr["armour_of_contempt_ap_worsen"] = spec
            root.special_rules = sr
            return True
        except Exception:
            raise
    def _clear_armour_of_contempt_for_attacker(self, attacker_unit: Any) -> None:
        key = self._attacker_unit_key(attacker_unit)
        if key is None:
            return
        try:
            units = list(getattr(self.player.get_army(), "units", []) or [])
        except Exception:
            raise
        for unit in units:
            try:
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                spec = sr.get("armour_of_contempt_ap_worsen")
                if not isinstance(spec, dict) or str(key) not in spec:
                    continue
                spec.pop(str(key), None)
                if not spec:
                    sr.pop("armour_of_contempt_ap_worsen", None)
                unit.special_rules = sr
            except Exception:
                raise
    def _queue_reaction(self, payload: Dict[str, Any], use_timer: bool = True) -> None:
        if not isinstance(payload, dict):
            return
        if use_timer:
            payload["expires_at"] = self._now() + float(self._reaction_timeout_s)
        payload["reaction"] = True
        self._pending_reactions.append(payload)

    def _prune_expired_reactions(self, now: Optional[float] = None) -> None:
        ts = self._now() if now is None else float(now)
        kept = []
        for r in list(self._pending_reactions):
            try:
                expires_at = r.get("expires_at", None)
                if expires_at is not None and ts >= float(expires_at):
                    continue
            except Exception:
                raise
            kept.append(r)
        self._pending_reactions = kept

    def _prune_reactions_for_phase(self) -> None:
        current = str(self._current_phase_name or "").strip().lower()
        if not current:
            return
        kept = []
        for r in list(self._pending_reactions):
            try:
                reaction_phase = r.get("phase_name") or r.get("phase")
            except Exception:
                raise
            if reaction_phase:
                if str(reaction_phase).strip().lower() != current:
                    continue
            kept.append(r)
        self._pending_reactions = kept

    def _reaction_time_left(self, reaction: Dict[str, Any], now: Optional[float] = None) -> Optional[float]:
        try:
            expires_at = reaction.get("expires_at", None)
            if expires_at is None:
                return None
            ts = self._now() if now is None else float(now)
            return max(0.0, float(expires_at) - ts)
        except Exception:
            raise
    def _is_implemented_stratagem(self, stratagem: Stratagem) -> bool:
        try:
            name_u = (stratagem.name or "").strip().upper()
            if name_u in IMPLEMENTED_STRATAGEM_NAMES:
                return True
            if self._get_defensive_reaction_spec(stratagem) is not None:
                return True
            if self._get_charge_melee_ap_spec(stratagem) is not None:
                return True
            return self._get_consolidate_move_spec(stratagem) is not None
        except Exception:
            raise
    @staticmethod
    def _normalize_timing_text(text: str) -> str:
        try:
            t = str(text or "").strip().lower()
        except Exception:
            raise
        return t.replace("\u2019", "'")

    @staticmethod
    def _is_bloodletters_unit(unit) -> bool:
        if unit is None:
            return False
        try:
            if hasattr(unit, "has_any_keyword") and unit.has_any_keyword("BLOODLETTERS"):
                return True
        except Exception:
            raise
        try:
            if hasattr(unit, "has_keyword") and unit.has_keyword("BLOODLETTERS"):
                return True
        except Exception:
            raise
        try:
            name = str(getattr(unit, "name", "") or "").strip().lower()
            if "bloodletters" in name:
                return True
        except Exception:
            raise
        return False

    def _turn_category(self, stratagem: Stratagem) -> str:
        try:
            phase = self._normalize_timing_text(getattr(stratagem, "phase", ""))
            turn = self._normalize_timing_text(getattr(stratagem, "turn", ""))

            if phase:
                if "opponent" in phase:
                    return "opponent"
                if "your " in phase:
                    return "your"
                if "any phase" in phase:
                    return "either"
                if "phase" in phase:
                    return "either"

            if turn:
                if "opponent" in turn:
                    return "opponent"
                if "your" in turn:
                    return "your"
                if "either" in turn or "any" in turn:
                    return "either"

            return "either"
        except Exception:
            raise
    def _effective_cp_cost(self, stratagem: Stratagem, context: Dict[str, Any]) -> int:
        target_unit = context.get("target_unit") or context.get("unit")
        cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        try:
            if hasattr(self.player, "preview_stratagem_cp_cost"):
                prev = self.player.preview_stratagem_cp_cost(stratagem, target_unit=target_unit)
                return int(prev.get("cost", cost))
        except Exception:
            raise
        return cost

    @staticmethod
    def _heroic_intervention_target_id(unit) -> Optional[str]:
        if unit is None:
            return None
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            return get_entity_id(root) or getattr(root, "_id", None)
        except Exception:
            return getattr(root, "_id", None)

    @staticmethod
    def _unit_has_faultless_opportunist(unit) -> bool:
        if unit is None:
            return False
        try:
            members = list(unit.get_attached_unit_members() or [])
        except Exception:
            members = []
        if not members:
            members = [unit]
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not sr.get("enhancement_faultless_opportunist", False):
                continue
            try:
                if callable(getattr(u, "is_alive", None)) and not u.is_alive():
                    continue
            except Exception:
                continue
            return True
        return False

    def _heroic_intervention_repeat_allowed(self, *, target_unit=None, candidates=None) -> bool:
        if target_unit is not None:
            if not self._unit_has_faultless_opportunist(target_unit):
                return False
            uid = self._heroic_intervention_target_id(target_unit)
            return bool(uid and uid not in self._heroic_intervention_units_this_phase)
        for cand in list(candidates or []):
            if not self._unit_has_faultless_opportunist(cand):
                continue
            uid = self._heroic_intervention_target_id(cand)
            if uid and uid not in self._heroic_intervention_units_this_phase:
                return True
        return False

    def _record_heroic_intervention_use(self, unit) -> None:
        uid = self._heroic_intervention_target_id(unit)
        if uid:
            self._heroic_intervention_units_this_phase.add(uid)

    def _evaluate_availability(
        self,
        stratagem: Stratagem,
        context: Dict[str, Any],
        *,
        is_active_turn: bool,
    ) -> Dict[str, Any]:
        result = {"available": False, "reason": None, "cp_cost": self._effective_cp_cost(stratagem, context)}
        name_u = (stratagem.name or "").strip().upper()
        phase_name = context.get("phase_name") or self._current_phase_name or ""

        if name_u and name_u in self._used_stratagems_this_phase:
            if name_u == "HEROIC INTERVENTION":
                if self._heroic_intervention_repeat_allowed(
                    target_unit=context.get("target_unit") or context.get("unit"),
                    candidates=context.get("candidates"),
                ):
                    pass
                else:
                    result["reason"] = "Already used this phase"
                    return result
            else:
                result["reason"] = "Already used this phase"
                return result
        if name_u and self._used_once_per_battle.get(name_u, False):
            result["reason"] = "Once per battle used"
            return result
        if name_u == "OVERWATCH" or name_u == "FIRE OVERWATCH":
            if self._used_this_turn.get("OVERWATCH", False):
                result["reason"] = "Already used this turn"
                return result
            enemy_unit = context.get("enemy_unit")
            try:
                if enemy_unit is not None and hasattr(enemy_unit, "has_first_prince_slaanesh_no_overwatch") and enemy_unit.has_first_prince_slaanesh_no_overwatch():
                    result["reason"] = "Target cannot be overwatched"
                    return result
            except Exception:
                raise
        if not stratagem.is_phase_allowed(phase_name):
            result["reason"] = "Wrong phase"
            return result
        if not stratagem.is_turn_allowed(is_active_turn):
            result["reason"] = "Wrong turn"
            return result

        if int(getattr(self.player, "command_points", 0) or 0) < int(result["cp_cost"] or 0):
            result["reason"] = "Not enough CP"
            return result

        # Targeting restrictions for provided context
        target = _extract_friendly_target_unit_from_kwargs(context)
        if target is not None and name_u not in ("BLOOD OFFERING", "A GRIM WARNING"):
            if _unit_cannot_be_target_of_stratagem(target):
                if name_u != "INSANE BRAVERY":
                    result["reason"] = "Target cannot be selected"
                    return result

        # Adeptus Custodes (Lions of the Emperor): UNLEASH THE LIONS
        if name_u == "UNLEASH THE LIONS":
            if self._unleash_lions_detachment_manager() is None:
                result["reason"] = "Wrong detachment"
                return result
            if target is not None:
                if not self._unleash_lions_is_valid_target(target):
                    result["reason"] = "Requires Allarus or Aquilon unit on battlefield"
                    return result
            else:
                if not self._unleash_lions_candidates():
                    result["reason"] = "Requires valid target"
                    return result

        # Last pass: delegate to stratagem conditions
        try:
            if name_u in ("BLOOD OFFERING", "A GRIM WARNING"):
                if context.get("objective_candidates"):
                    result["available"] = True
                    result["reason"] = None
                    return result
            if name_u == "BLITZING FIREPOWER":
                if self._blitzing_firepower_candidates():
                    result["available"] = True
                    result["reason"] = None
                    return result
            if name_u == "MERCILESS RECLAMATION":
                if self._starshatter_merciless_reclamation_candidates(phase_name):
                    result["available"] = True
                    result["reason"] = None
                    return result
            if name_u == "DIMENSIONAL TUNNEL":
                if self._starshatter_dimensional_tunnel_candidates():
                    result["available"] = True
                    result["reason"] = None
                    return result
            if name_u == "CHRONOSHIFT":
                if self._starshatter_chronoshift_candidates():
                    result["available"] = True
                    result["reason"] = None
                    return result
            if stratagem.can_use(self.player, self.game, **context):
                result["available"] = True
                result["reason"] = None
                return result
        except Exception:
            raise
        result["reason"] = "Requires valid trigger or target"
        return result

    def _reaction_target_label(self, reaction: Dict[str, Any]) -> str:
        try:
            if reaction.get("enemy_unit") is not None:
                return f"Vs {getattr(reaction['enemy_unit'], 'name', 'Enemy')}"
            if reaction.get("target_unit") is not None:
                return f"Target: {getattr(reaction['target_unit'], 'name', 'Unit')}"
            if reaction.get("unit") is not None:
                return f"Target: {getattr(reaction['unit'], 'name', 'Unit')}"
            if reaction.get("target_model") is not None:
                return f"Target model: {getattr(reaction['target_model'], 'name', 'Model')}"
        except Exception:
            raise
        try:
            hint = self._stratagem_target_hint(reaction.get("stratagem", ""))
        except Exception:
            raise
        if hint:
            return hint
        return ""

    @staticmethod
    def _stratagem_target_hint(name: str) -> str:
        name_u = (name or "").strip().upper()
        hints = {
            "A GRIM WARNING": "Objective: destroyed BLOOD ANGELS unit on your objective",
            "ARMOUR OF CONTEMPT": "Target: ADEPTUS ASTARTES unit",
            "DEATHLESS DUTY": "Target: DEATH COMPANY unit",
            "INSENSATE RAMPAGE": "Target: DEATH COMPANY unit",
            "LIMB FROM LIMB": "Target: BLOOD ANGELS unit (charged)",
            "RED WRATH": "Target: BLOOD ANGELS unit (advanced)",
        }
        return hints.get(name_u, "")

    def _is_warhost_detachment(self) -> bool:
        try:
            army = self.player.get_army()
        except Exception:
            raise
        mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
        if mgr is None:
            return False
        try:
            return bool(mgr.is_warhost_detachment())
        except Exception:
            raise

    def _get_necrons_mgr(self):
        try:
            army = self.player.get_army()
        except Exception:
            raise
        return getattr(army, "necrons_detachments", None) if army is not None else None

    def _is_starshatter_arsenal(self) -> bool:
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return False
        try:
            return bool(mgr.is_starshatter_arsenal())
        except Exception:
            raise
    def _blitzing_firepower_candidates(self) -> List[Any]:
        if not self._is_warhost_detachment():
            return []
        try:
            army = self.player.get_army()
        except Exception:
            raise
        units = list(getattr(army, "units", []) or []) if army is not None else []
        candidates: List[Any] = []
        seen = set()
        for unit in units:
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            try:
                uid = get_entity_id(root)
            except Exception:
                raise
            if uid in seen:
                continue
            seen.add(uid)
            try:
                if not root.is_alive():
                    continue
            except Exception:
                raise
            try:
                if not getattr(root, "deployed", False):
                    continue
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    continue
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    continue
            except Exception:
                raise
            try:
                if not root.has_any_keyword("ASURYANI"):
                    continue
            except Exception:
                raise
            try:
                if getattr(getattr(root, "round_state", None), "shot_this_round", False):
                    continue
            except Exception:
                raise
            candidates.append(root)
        return candidates

    def _starshatter_candidates(
        self,
        *,
        require_vehicle_or_mounted: bool = False,
        require_not_moved: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
    ) -> List[Any]:
        if not self._is_starshatter_arsenal():
            return []
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return []
        try:
            army = self.player.get_army()
        except Exception:
            raise
        units = list(getattr(army, "units", []) or []) if army is not None else []
        candidates: List[Any] = []
        seen = set()
        for unit in units:
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                continue
            try:
                uid = get_entity_id(root)
            except Exception:
                raise
            if uid in seen:
                continue
            seen.add(uid)
            try:
                if not root.is_alive():
                    continue
            except Exception:
                raise
            try:
                if not getattr(root, "deployed", False):
                    continue
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    continue
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    continue
            except Exception:
                raise
            try:
                if not mgr.unit_is_necrons(root):
                    continue
                if mgr.unit_is_titanic(root):
                    continue
            except Exception:
                raise
            if require_vehicle_or_mounted:
                try:
                    if not mgr.unit_is_vehicle_or_mounted(root):
                        continue
                except Exception:
                    raise
            if require_not_moved:
                try:
                    if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
                        continue
                except Exception:
                    raise
            if require_not_shot:
                try:
                    if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                        continue
                except Exception:
                    raise
            if require_not_fought:
                try:
                    if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                        continue
                except Exception:
                    raise
            candidates.append(root)
        return candidates

    def _starshatter_merciless_reclamation_candidates(self, phase_name: str | None = None) -> List[Any]:
        phase_key = str(phase_name or "").strip().lower()
        require_not_shot = "shooting" in phase_key
        require_not_fought = "fight" in phase_key
        return self._starshatter_candidates(
            require_vehicle_or_mounted=False,
            require_not_shot=require_not_shot,
            require_not_fought=require_not_fought,
        )

    def _starshatter_dimensional_tunnel_candidates(self) -> List[Any]:
        return self._starshatter_candidates(require_vehicle_or_mounted=True)

    def _starshatter_chronoshift_candidates(self) -> List[Any]:
        return self._starshatter_candidates(require_vehicle_or_mounted=True, require_not_moved=True)

    def _unit_wholly_within_battlefield_edge_distance(self, unit, distance: float) -> bool:
        if unit is None:
            return False
        try:
            dist = float(distance)
        except Exception:
            raise
        if dist <= 0.0:
            return False
        try:
            game = self.game
        except Exception:
            raise
        width = None
        height = None
        try:
            bf = getattr(game, "battlefield", None)
            width = getattr(bf, "width", None)
            height = getattr(bf, "height", None)
        except Exception:
            raise
        if width is None or height is None:
            try:
                game_map = getattr(game, "map", None)
                width = getattr(game_map, "width", None)
                height = getattr(game_map, "height", None)
            except Exception:
                raise
        if width is None or height is None:
            return False
        try:
            models = unit.get_attached_unit_models()
        except Exception:
            raise
        if not models:
            return False
        for m in models:
            try:
                if not getattr(m, "is_alive", True):
                    continue
            except Exception:
                raise
            base = getattr(m, "model_base", None)
            if base is None:
                return False
            try:
                x = float(getattr(base, "x", 0.0))
                y = float(getattr(base, "y", 0.0))
            except Exception:
                raise
            try:
                r = float(getattr(base, "get_radius", lambda: 0.0)())
            except Exception:
                raise
            within = (
                (x - r) <= dist + 1e-6 or
                ((float(width) - x) - r) <= dist + 1e-6 or
                (y - r) <= dist + 1e-6 or
                ((float(height) - y) - r) <= dist + 1e-6
            )
            if not within:
                return False
        return True

    def _return_destroyed_models_full(
        self,
        unit,
        *,
        amount: int,
        game_map=None,
        skip_character: bool = False,
    ) -> int:
        if unit is None:
            return 0
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            raise
        if root is None:
            return 0
        try:
            destroyed = list(getattr(root, "models_lost", []) or [])
        except Exception:
            raise
        if not destroyed:
            return 0
        if skip_character:
            filtered = []
            for m in destroyed:
                try:
                    if bool(getattr(m, "is_character", False)):
                        continue
                except Exception:
                    raise
                filtered.append(m)
            destroyed = filtered
        if not destroyed:
            return 0
        to_return = destroyed[: max(0, int(amount or 0))]
        if not to_return:
            return 0
        try:
            alive_models = [m for m in (getattr(root, "models", []) or []) if getattr(m, "is_alive", True)]
        except Exception:
            raise
        returned = 0
        for model in to_return:
            try:
                if hasattr(root, "models_lost") and model in root.models_lost:
                    root.models_lost.remove(model)
            except Exception:
                raise
            try:
                if hasattr(model, "set_parent_unit"):
                    model.set_parent_unit(root)
                else:
                    model.parent_unit = root
            except Exception:
                raise
            try:
                base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
                if base_wounds:
                    model.wounds = base_wounds
            except Exception:
                raise
            try:
                if hasattr(model, "_check_damaged_profile"):
                    model._check_damaged_profile()
            except Exception:
                raise
            try:
                setattr(model, "_on_death_reactions_resolved", False)
                setattr(model, "_fight_on_death_used", False)
                setattr(model, "_shoot_on_death_used", False)
            except Exception:
                raise
            added = False
            try:
                existing = list(getattr(root, "models", []) or [])
                if any(model is m for m in existing):
                    added = True
                elif any(getattr(model, "id", None) == getattr(m, "id", None) for m in existing):
                    root.models.append(model)
                    added = True
                elif hasattr(root, "add_model"):
                    root.add_model(model)
                    added = True
                else:
                    root.models.append(model)
                    added = True
            except Exception:
                raise
            if not added:
                try:
                    root.models.append(model)
                except Exception:
                    raise
            # Attempt to place the model near the unit coherently
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
                    if pos is not None and hasattr(model, "set_location"):
                        model.set_location(*pos)
            except Exception:
                raise
            alive_models.append(model)
            try:
                if hasattr(root, "update_coherency"):
                    root.update_coherency()
            except Exception:
                raise
            returned += 1
        return returned

    def _skyborne_transport_candidates(self, unit) -> List[Any]:
        if unit is None:
            return []
        try:
            game = self.game
        except Exception:
            raise
        game_map = getattr(game, "map", None) if game is not None else None
        try:
            army = unit.get_parent_army()
        except Exception:
            raise
        if army is None:
            return []
        try:
            from ..utility.aura_utils import unit_wholly_within_range_of_unit
        except Exception:
            raise
        transports: List[Any] = []
        for t in list(getattr(army, "units", []) or []):
            try:
                if t is None or not t.is_alive():
                    continue
                if not getattr(t, "deployed", False):
                    continue
                if not bool(getattr(t, "is_transport", False)):
                    continue
                if not t.can_transport(unit):
                    continue
                if callable(unit_wholly_within_range_of_unit):
                    if not unit_wholly_within_range_of_unit(t, unit, 6.0, use_attached_aggregate=True):
                        continue
                transports.append(t)
            except Exception:
                raise
        return transports

    def _build_available(self) -> None:
        """
        Chapter Approved scope:
        - Always include global core stratagems.
        - If the player has a faction/detachment, include matching faction/detachment stratagems.
        - Exclude Boarding Actions / Challenger / other game modes.
        """
        army = None
        try:
            army = self.player.get_army() if self.player else None
        except Exception:
            raise
        faction_id = getattr(army, "faction_id", None)
        detachment = getattr(army, "detachment_type", None)
        raw = self._waha.get_stratagems_for_faction(faction_id=faction_id, detachment=detachment)
        tnorm = lambda t: (t or "").strip().lower()
        filtered: list[dict] = []
        for s in list(raw or []):
            try:
                is_global = not (s.get("faction_id") or "").strip()
                tt = tnorm(s.get("type"))
                if "boarding actions" in tt or "boarding action" in tt:
                    continue
                if "challenger" in tt:
                    continue
                if is_global:
                    # Keep only core + core stratagem variants
                    if not (tt.startswith("core ") or tt.startswith("core\u00a0") or tt.startswith("core\u2013") or tt.startswith("core-") or tt.startswith("core stratagem")):
                        # For safety, also keep "core -" variants that might not start with "core " due to unicode dashes.
                        if "core" not in tt:
                            continue
                        if "core stratagem" not in tt and "core \u2013" not in tt and "core -" not in tt:
                            continue
                entry = dict(s)
                name_u = (entry.get("name", "") or "").strip().upper()
                if name_u == "APOPLECTIC FRENZY":
                    entry["phase"] = "Movement phase"
                filtered.append(entry)
            except Exception:
                raise
        # Deduplicate by name: keep the newest/highest id for each name (case-insensitive).
        def _id_key(entry: dict) -> int:
            try:
                return int((entry.get("id") or "0").strip())
            except Exception:
                raise
        by_name: dict[str, dict] = {}
        for entry in filtered:
            name_key = (entry.get("name", "") or "").strip().lower()
            if not name_key:
                continue
            prev = by_name.get(name_key)
            if prev is None or _id_key(entry) > _id_key(prev):
                by_name[name_key] = entry
        unique = list(by_name.values())
        # Stable ordering
        unique.sort(key=lambda e: ((e.get("name") or "").strip().lower(), -_id_key(e)))
        self.available = [Stratagem.from_json(s) for s in unique]

    def _subscribe_events(self, *, event_system=None, group: Optional[str] = None) -> None:
        if not self.game:
            self.game = getattr(self.player, "game", None)
        es = event_system or (getattr(self.game, "event_system", None) if self.game is not None else None)
        if es is None:
            return
        group_name = group or self._event_group
        if group_name:
            self._event_group = group_name
        required = self._compute_required_handlers()
        self._required_events = set(required.keys())
        for event_name, handler_list in required.items():
            for handler in handler_list:
                key = (event_name, getattr(handler, "__name__", str(handler)))
                if key in self._subscribed_handlers:
                    continue
                try:
                    if group_name:
                        es.subscribe(event_name, handler, group=group_name)
                    else:
                        es.subscribe(event_name, handler)
                except Exception:
                    raise
                self._subscribed_handlers[key] = handler

    def _unsubscribe_events(self, *, event_system=None, group: Optional[str] = None) -> None:
        es = event_system or (getattr(self.game, "event_system", None) if self.game is not None else None)
        group_name = group or self._event_group
        for (event_name, _key), handler in list(self._subscribed_handlers.items()):
            if es is None:
                continue
            try:
                if group_name:
                    es.unsubscribe(event_name, handler, group=group_name)
                else:
                    es.unsubscribe(event_name, handler)
            except Exception:
                pass
        self._subscribed_handlers = {}
        self._required_events = set()

    # -------- Event handlers --------
    def _on_phase_start(self, player, phase, **kwargs):
        # Clear per-phase transient allowances
        self._last_failed_battle_shock_unit = None
        try:
            self._worthy_skull_kills = {}
        except Exception:
            raise
        # Track phase for phase-aware filtering
        try:
            # Phase may be an Enum; normalize to a friendly string
            name = getattr(phase, 'name', None)
            if name:
                # Convert ENUM_NAME to 'Name phase'
                name_map = {
                    'COMMAND_PHASE': 'Command phase',
                    'MOVEMENT_PHASE': 'Movement phase',
                    'SHOOTING_PHASE': 'Shooting phase',
                    'CHARGE_PHASE': 'Charge phase',
                    'FIGHT_PHASE': 'Fight phase',
                }
                self._current_phase_name = name_map.get(name, name.title().replace('_', ' '))
            else:
                # If provided as string already
                self._current_phase_name = str(phase)
        except Exception:
            raise
        try:
            self._prune_reactions_for_phase()
        except Exception:
            raise
        try:
            if hasattr(self, "_recent_shooting_targets"):
                self._recent_shooting_targets.clear()
        except Exception:
            raise
        # Reset once-per-turn limits on your turn start
        try:
            is_active_turn = player is self.player
            if is_active_turn and getattr(phase, 'name', None) == 'COMMAND_PHASE':
                self._used_this_turn['OVERWATCH'] = False
        except Exception:
            raise
        try:
            self._used_stratagems_this_phase.clear()
        except Exception:
            raise
        try:
            if not hasattr(self, "_heroic_intervention_units_this_phase"):
                self._heroic_intervention_units_this_phase = set()
            else:
                self._heroic_intervention_units_this_phase.clear()
        except Exception:
            raise

    def _gilded_champion_detachment_manager(self):
        army = getattr(self.player, "army", None)
        if army is None:
            return None
        mgr = getattr(army, "adeptus_custodes_detachments", None)
        if mgr is None or not hasattr(mgr, "is_lions_of_the_emperor"):
            return None
        if not mgr.is_lions_of_the_emperor():
            return None
        return mgr

    def _unleash_lions_detachment_manager(self):
        return self._gilded_champion_detachment_manager()

    @staticmethod
    def _unleash_lions_normalize_name(name: str) -> str:
        name = str(name or "").lower()
        name = re.sub(r"[^a-z0-9]+", " ", name).strip()
        return " ".join(name.split())

    def _unleash_lions_is_allarus_or_aquilon(self, unit) -> bool:
        if unit is None:
            return False
        name = self._unleash_lions_normalize_name(getattr(unit, "name", ""))
        tokens = set(name.split())
        if ("allarus" in tokens) and ("custodian" in tokens or "custodians" in tokens):
            return True
        if ("aquilon" in tokens) and ("custodian" in tokens or "custodians" in tokens):
            return True
        return False

    def _unleash_lions_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        active_fn = getattr(unit, "is_active_for_rules", None)
        if callable(active_fn):
            return bool(active_fn())
        try:
            if not bool(getattr(unit, "deployed", False)):
                return False
            if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
                return False
            if bool(getattr(unit, "is_embarked", False)) or getattr(unit, "embarked_in", None) is not None:
                return False
        except Exception:
            return False
        return True

    def _unleash_lions_is_valid_target(self, unit) -> bool:
        if unit is None:
            return False
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None:
            return False
        army = getattr(self.player, "army", None)
        if army is None:
            return False
        try:
            if hasattr(root, "get_parent_army") and root.get_parent_army() is not army:
                return False
        except Exception:
            return False
        if not self._unleash_lions_is_allarus_or_aquilon(root):
            return False
        if not self._unleash_lions_on_battlefield(root):
            return False
        return True

    def _unleash_lions_candidates(self) -> List[Any]:
        mgr = self._unleash_lions_detachment_manager()
        if mgr is None:
            return []
        army = getattr(self.player, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        candidates: List[Any] = []
        for unit in list(getattr(army, "units", []) or []):
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            if root is None:
                continue
            rid = get_entity_id(root)
            if rid and rid in seen:
                continue
            if rid:
                seen.add(rid)
            if self._unleash_lions_is_valid_target(root):
                candidates.append(root)
        return candidates

    @staticmethod
    def _gilded_champion_target_root(model):
        unit = getattr(model, "parent_unit", None) if model is not None else None
        if unit is None:
            return None
        if hasattr(unit, "get_attached_unit_root"):
            return unit.get_attached_unit_root()
        return unit

    def _resolve_gilded_champion_model(self, kwargs: Dict[str, Any]):
        model = kwargs.get("model")
        if model is not None:
            return model
        model_id = str(kwargs.get("model_id", "") or "")
        if not model_id:
            return None
        game = self.game or getattr(self.player, "game", None)
        registry = getattr(game, "entity_registry", None) if game is not None else None
        if registry is None or not hasattr(registry, "get"):
            return None
        return registry.get(model_id, kind="model")

    def _gilded_champion_resolve_phase_name(self, phase_name: str, game) -> str:
        text = str(phase_name or "").strip()
        if text:
            return text
        if self._current_phase_name:
            return str(self._current_phase_name)
        label_fn = getattr(game, "_current_phase_label", None) if game is not None else None
        if callable(label_fn):
            return str(label_fn() or "")
        return ""

    def _gilded_champion_prepare(
        self,
        *,
        model,
        ability_key: str,
        ability_name: str,
        phase_name: str,
        source: str,
        game=None,
    ) -> Optional[Dict[str, Any]]:
        if model is None:
            return None
        source_key = str(source or "").strip().lower()
        if source_key != "datasheet":
            return None
        ability_key_norm = str(ability_key or "").strip().lower()
        if not ability_key_norm:
            return None
        detachment_mgr = self._gilded_champion_detachment_manager()
        if detachment_mgr is None:
            return None
        stratagem = self.get_by_name("GILDED CHAMPION")
        if stratagem is None:
            return None
        if game is None:
            game = getattr(self.player, "game", None)
        if game is None:
            return None
        if self.game is None:
            self.game = game
        root = self._gilded_champion_target_root(model)
        if root is None:
            return None
        army = getattr(self.player, "army", None)
        if army is None or not hasattr(root, "get_parent_army"):
            return None
        if root.get_parent_army() is not army:
            return None
        has_any_kw = getattr(root, "has_any_keyword", None)
        has_custodes_kw = bool(has_any_kw("ADEPTUS CUSTODES")) if callable(has_any_kw) else False
        root_faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if not has_custodes_kw and root_faction_id != "AC":
            return None
        is_character = bool(getattr(model, "is_character", False))
        if not is_character and callable(has_any_kw):
            is_character = bool(has_any_kw("CHARACTER"))
        if not is_character:
            return None
        model_id = get_entity_id(model)
        if not model_id or model_id in self._gilded_champion_used_models:
            return None
        resolved_phase_name = self._gilded_champion_resolve_phase_name(phase_name, game)
        active_player = getattr(game, "get_current_player", lambda: None)()
        is_active_turn = active_player is self.player
        context = {
            "phase_name": resolved_phase_name,
            "target_unit": root,
            "unit": root,
            "model": model,
            "model_id": model_id,
        }
        availability = self._evaluate_availability(stratagem, context, is_active_turn=is_active_turn)
        if not availability.get("available", False):
            return None
        ability_label = str(ability_name or "").strip() or ability_key_norm.replace("_", " ").title()
        return {
            "stratagem": stratagem,
            "model": model,
            "model_id": model_id,
            "target_unit": root,
            "phase_name": resolved_phase_name,
            "ability_key": ability_key_norm,
            "ability_name": ability_label,
            "source": source_key,
            "cp_cost": int(availability.get("cp_cost", stratagem.cp_cost) or stratagem.cp_cost),
        }

    def _gilded_champion_has_pending_decision(self, game, *, model_id: str, ability_key: str) -> bool:
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_USE_GILDED_CHAMPION

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_USE_GILDED_CHAMPION:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("model_id", "") or "") != str(model_id):
                continue
            if str(ctx.get("ability_key", "") or "") != str(ability_key):
                continue
            return True
        return False

    def _queue_gilded_champion_decision(self, game, prepared: Dict[str, Any]) -> None:
        if self._gilded_champion_has_pending_decision(
            game,
            model_id=str(prepared.get("model_id", "") or ""),
            ability_key=str(prepared.get("ability_key", "") or ""),
        ):
            return
        from ..engine.decision_kinds import DECISION_USE_GILDED_CHAMPION
        from ..engine.decisions import DecisionOption, DecisionRequest

        model_id = str(prepared.get("model_id", "") or "")
        ability_key = str(prepared.get("ability_key", "") or "")
        ability_name = str(prepared.get("ability_name", "") or ability_key)
        phase_name = str(prepared.get("phase_name", "") or "")
        unit = prepared.get("target_unit")
        unit_id = get_entity_id(unit) if unit is not None else ""
        army = getattr(self.player, "army", None)
        army_id = get_entity_id(army) if army is not None else ""
        base_payload = {
            "stratagem_name": "GILDED CHAMPION",
            "model_id": model_id,
            "unit_id": unit_id,
            "army_id": army_id,
            "ability_key": ability_key,
            "ability_name": ability_name,
            "phase_name": phase_name,
            "source": str(prepared.get("source", "datasheet") or "datasheet"),
        }
        options = [
            DecisionOption.create(
                f"Use Gilded Champion ({ability_name})",
                payload=dict(base_payload, action="use"),
            ),
            DecisionOption.create("None", payload=dict(base_payload, action="skip", skip=True)),
        ]
        req = DecisionRequest.create(
            DECISION_USE_GILDED_CHAMPION,
            f"Gilded Champion: {ability_name}",
            player_id=getattr(self.player, "id", None),
            options=options,
            context=base_payload,
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)
            return
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "add"):
            queue.add(req)

    def _publish_gilded_champion_prompt(self, game, prepared: Dict[str, Any]) -> bool:
        event_system = getattr(game, "event_system", None)
        if event_system is None or not hasattr(event_system, "publish"):
            return False
        has_control = bool(getattr(self.player, "has_control", lambda: False)())
        if not has_control:
            return False
        payload = dict(prepared)
        payload.update({"player": self.player, "game": game})
        event_system.publish("gilded_champion_prompt", **payload)
        return True

    def _on_once_per_battle_ability_used(
        self,
        player=None,
        model=None,
        ability_key: str = "",
        ability_name: str = "",
        phase_name: str = "",
        source: str = "",
        game=None,
        **_kwargs,
    ):
        if player is not self.player:
            return
        if game is None:
            game = getattr(self.player, "game", None)
        prepared = self._gilded_champion_prepare(
            model=model,
            ability_key=ability_key,
            ability_name=ability_name,
            phase_name=phase_name,
            source=source,
            game=game,
        )
        if prepared is None or game is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            self._queue_gilded_champion_decision(game, prepared)
            return
        if self._publish_gilded_champion_prompt(game, prepared):
            return
        ctx = {
            "ability_name": prepared.get("ability_name", ""),
            "phase": prepared.get("phase_name", ""),
            "model": getattr(prepared.get("model"), "name", ""),
        }
        should_fn = getattr(self.player, "_should_use_optional_ability", None)
        should_use = bool(should_fn("GILDED_CHAMPION", ctx)) if callable(should_fn) else False
        if not should_use:
            return
        self.use(
            "GILDED CHAMPION",
            model=prepared.get("model"),
            ability_key=prepared.get("ability_key", ""),
            ability_name=prepared.get("ability_name", ""),
            phase_name=prepared.get("phase_name", ""),
            source=prepared.get("source", "datasheet"),
            target_unit=prepared.get("target_unit"),
        )

    def _on_phase_end(self, player, phase, **kwargs):
        # Queue NEW ORDERS at end of your Command phase
        try:
            is_your_turn = player is self.player
            phase_name = getattr(phase, 'name', None)
            if is_your_turn and phase_name == 'COMMAND_PHASE':
                s = self.get_by_name('NEW ORDERS')
                if s and s.can_use(self.player, self.game, phase_name='Command phase'):
                    if getattr(self.player, 'active_secondaries', None) and self.player.can_draw_secondary():
                        # Deduplicate if already present for this phase end
                        already = False
                        for r in self._pending_reactions:
                            if r.get('event') == 'phase_end' and r.get('stratagem') == s.name and r.get('phase') == 'Command phase':
                                already = True
                                break
                        if not already:
                            self._queue_reaction({
                                'event': 'phase_end',
                                'phase': 'Command phase',
                                'phase_name': 'Command phase',
                                'stratagem': s.name,
                                'cp_cost': s.cp_cost,
                                'options': [c for c in self.player.active_secondaries],
                            }, use_timer=False)
        except Exception:
            raise
        # Clear command-phase battle-shock suppression flags (e.g., Terrifying Spectacle).
        try:
            phase_name = getattr(phase, "name", None)
            if phase_name == "COMMAND_PHASE" and self.game is not None:
                for p in list(getattr(self.game, "players", []) or []):
                    army = getattr(p, "get_army", lambda: None)()
                    for u in list(getattr(army, "units", []) or []):
                        try:
                            sr = getattr(u, "special_rules", None)
                            if not isinstance(sr, dict):
                                continue
                            if "battle_shock_suppress_other_tests_phase" in sr:
                                sr.pop("battle_shock_suppress_other_tests_phase", None)
                                sr.pop("battle_shock_suppress_other_tests_source", None)
                                sr.pop("battle_shock_allow_suppressed_test", None)
                                u.special_rules = sr
                        except Exception:
                            raise
        except Exception:
            raise
        # Clear end-of-phase defensive buffs (e.g. GO TO GROUND) to avoid leaking into later phases (e.g. Overwatch).
        try:
            phase_name = getattr(phase, 'name', None)
            if phase_name == 'SHOOTING_PHASE':
                for u in list(getattr(self.player.get_army(), "units", []) or []):
                    try:
                        sr = getattr(u, "special_rules", None)
                        if isinstance(sr, dict) and sr.get("go_to_ground_active") is True:
                            sr.pop("go_to_ground_active", None)
                            u.special_rules = sr
                        if isinstance(sr, dict) and sr.get("smokescreen_active") is True:
                            sr.pop("smokescreen_active", None)
                            u.special_rules = sr
                        if isinstance(sr, dict) and sr.get("blitzing_firepower_active") is True:
                            sr.pop("blitzing_firepower_active", None)
                            sr.pop("blitzing_firepower_expires_phase", None)
                            u.special_rules = sr
                        if isinstance(sr, dict) and sr.get("lightning_fast_reactions_active") is True:
                            sr.pop("lightning_fast_reactions_active", None)
                            sr.pop("lightning_fast_reactions_expires_phase", None)
                            u.special_rules = sr
                    except Exception:
                        raise
        except Exception:
            raise
        # Clear end-of-phase defensive buffs for Fight phase.
        try:
            phase_name = getattr(phase, 'name', None)
            if phase_name == 'FIGHT_PHASE':
                if player is self.player:
                    self._record_ec_last_turn_flags()
                for u in list(getattr(self.player.get_army(), "units", []) or []):
                    try:
                        sr = getattr(u, "special_rules", None)
                        if isinstance(sr, dict) and sr.get("lightning_fast_reactions_active") is True:
                            sr.pop("lightning_fast_reactions_active", None)
                            sr.pop("lightning_fast_reactions_expires_phase", None)
                        if isinstance(sr, dict) and sr.get("daemonic_fury_twin_linked_active") is True:
                            sr.pop("daemonic_fury_twin_linked_active", None)
                            sr.pop("daemonic_fury_twin_linked_expires_phase", None)
                        if isinstance(sr, dict) and sr.get("daemonic_fury_lance_active") is True:
                            sr.pop("daemonic_fury_lance_active", None)
                            sr.pop("daemonic_fury_lance_turn_owner", None)
                            sr.pop("daemonic_fury_lance_turn", None)
                        if isinstance(sr, dict) and sr.get("death_ecstasy_active") is True:
                            sr.pop("death_ecstasy_active", None)
                            sr.pop("death_ecstasy_expires_phase", None)
                            sr.pop("death_ecstasy_source", None)
                        if isinstance(sr, dict) and sr.get("deathless_duty_active") is True:
                            sr.pop("deathless_duty_active", None)
                            sr.pop("deathless_duty_expires_phase", None)
                            sr.pop("deathless_duty_source", None)
                        u.special_rules = sr
                    except Exception:
                        raise
        except Exception:
            raise
        # Clear end-of-phase Necrons stratagem buffs (Movement/Shooting/Fight).
        try:
            phase_name = getattr(phase, "name", None)
            if phase_name in ("MOVEMENT_PHASE", "SHOOTING_PHASE", "FIGHT_PHASE"):
                units = list(getattr(self.player.get_army(), "units", []) or [])
                seen = set()
                for unit in units:
                    try:
                        root = unit.get_attached_unit_root()
                    except Exception:
                        root = unit
                    if root is None:
                        continue
                    try:
                        uid = get_entity_id(root)
                    except Exception:
                        uid = None
                    if uid and uid in seen:
                        continue
                    if uid:
                        seen.add(uid)
                    try:
                        sr = getattr(root, "special_rules", None)
                    except Exception:
                        sr = None
                    if not isinstance(sr, dict):
                        continue
                    if phase_name == "MOVEMENT_PHASE":
                        exp = str(sr.get("chronoshift_expires_phase", "") or "").strip().upper()
                        if sr.get("chronoshift_active") and (not exp or exp == "MOVEMENT_PHASE"):
                            sr.pop("chronoshift_active", None)
                            sr.pop("chronoshift_expires_phase", None)
                        exp = str(sr.get("dimensional_tunnel_expires_phase", "") or "").strip().upper()
                        if sr.get("dimensional_tunnel_active") and (not exp or exp == "MOVEMENT_PHASE"):
                            added = set(sr.get("dimensional_tunnel_added_phase_move_types") or [])
                            if added:
                                current = list(sr.get("bearer_unit_phase_move_types") or [])
                                kept = [t for t in current if t not in added]
                                if kept:
                                    sr["bearer_unit_phase_move_types"] = kept
                                else:
                                    sr.pop("bearer_unit_phase_move_types", None)
                            sr.pop("dimensional_tunnel_added_phase_move_types", None)
                            sr.pop("dimensional_tunnel_active", None)
                            sr.pop("dimensional_tunnel_expires_phase", None)
                    if phase_name in ("SHOOTING_PHASE", "FIGHT_PHASE"):
                        exp = str(sr.get("merciless_reclamation_expires_phase", "") or "").strip().upper()
                        if sr.get("merciless_reclamation_active") and (not exp or exp == phase_name):
                            sr.pop("merciless_reclamation_active", None)
                            sr.pop("merciless_reclamation_expires_phase", None)
                    root.special_rules = sr
        except Exception:
            raise
        # Clear generic defensive reaction effects at phase end.
        try:
            phase_name = getattr(phase, "name", None)
            if phase_name in ("SHOOTING_PHASE", "FIGHT_PHASE"):
                self._clear_defensive_effects_for_phase(phase_name)
        except Exception:
            raise
        # Clear end-of-phase offensive buffs (e.g. EPIC CHALLENGE) to avoid leaking into later phases.
        try:
            phase_name = getattr(phase, "name", None)
            if phase_name == "FIGHT_PHASE":
                for m in list(getattr(self, "_epic_challenge_models", []) or []):
                    try:
                        sr = getattr(m, "special_rules", None)
                        if isinstance(sr, dict) and sr.get("epic_challenge_precision_active") is True:
                            sr.pop("epic_challenge_precision_active", None)
                            m.special_rules = sr
                    except Exception:
                        raise
                self._epic_challenge_models = []
                for u in list(getattr(self.player.get_army(), "units", []) or []):
                    try:
                        sr = getattr(u, "special_rules", None)
                        if not isinstance(sr, dict):
                            continue
                        if sr.get("hack_and_slash_active") is True:
                            sr.pop("hack_and_slash_active", None)
                            sr.pop("hack_and_slash_ap_bonus", None)
                            sr.pop("hack_and_slash_expires_phase", None)
                        if sr.get("charge_melee_ap_bonus", 0):
                            sr.pop("charge_melee_ap_bonus", None)
                            sr.pop("charge_melee_ap_bonus_expires_phase", None)
                            sr.pop("charge_melee_ap_bonus_source", None)
                        if sr.get("limb_from_limb_melee_strength_bonus", 0) or sr.get("limb_from_limb_melee_ap_bonus", 0):
                            sr.pop("limb_from_limb_melee_strength_bonus", None)
                            sr.pop("limb_from_limb_melee_ap_bonus", None)
                            sr.pop("limb_from_limb_expires_phase", None)
                            sr.pop("limb_from_limb_source", None)
                        if (
                            "stratagem_consolidate_distance_override" in sr
                            or sr.get("stratagem_consolidate_requires_engagement")
                        ):
                            sr.pop("stratagem_consolidate_distance_override", None)
                            sr.pop("stratagem_consolidate_requires_engagement", None)
                            sr.pop("stratagem_consolidate_expires_phase", None)
                            sr.pop("stratagem_consolidate_source", None)
                        if sr.get("frenzied_resilience_active") is True:
                            sr.pop("frenzied_resilience_active", None)
                            sr.pop("frenzied_resilience_damage_reduction", None)
                            sr.pop("frenzied_resilience_expires_phase", None)
                        u.special_rules = sr
                    except Exception:
                        raise
        except Exception:
            raise
        # Queue RAPID INGRESS at end of opponent's Movement phase
        try:
            # Event supplies the active player as `player`. We offer this to the NON-active player.
            is_opponents_turn = player is not self.player
            phase_name = getattr(phase, 'name', None)
            if is_opponents_turn and phase_name == 'MOVEMENT_PHASE':
                s = self.get_by_name('RAPID INGRESS')
                if not s:
                    return
                # Must have at least one eligible unit in Reserves that could arrive this battle round
                candidates = []
                try:
                    # Prefer Game helper if present
                    if hasattr(self.game, 'get_units_that_can_arrive_from_reserves'):
                        candidates = list(self.game.get_units_that_can_arrive_from_reserves(self.player))
                    else:
                        candidates = [u for u in getattr(self.player.get_army(), 'units', []) or []
                                      if getattr(u, 'is_in_reserves', lambda: False)()
                                      and getattr(u, 'can_arrive_from_reserves', lambda _t: False)(getattr(self.game, 'turn', 0))]
                except Exception:
                    raise
                if not candidates:
                    return
                # Timing checks (CP/turn/phase)
                if not s.can_use(self.player, self.game, phase_name='Movement phase'):
                    return
                # Deduplicate per phase end
                for r in self._pending_reactions:
                    if r.get('event') == 'phase_end' and str(r.get('stratagem', '')).upper() == 'RAPID INGRESS':
                        return
                self._queue_reaction({
                    'event': 'phase_end',
                    'phase': 'Movement phase',
                    'phase_name': 'Movement phase',
                    'stratagem': s.name,
                    'cp_cost': s.cp_cost,
                    'candidates': candidates,
                        })
        except Exception:
            raise
        # Warhost: SKYBORNE SANCTUARY (end of Fight phase, either player's turn)
        try:
            phase_name = getattr(phase, "name", None)
            if phase_name == "FIGHT_PHASE":
                s = self.get_by_name("SKYBORNE SANCTUARY")
                if not s:
                    pass
                elif not self._is_warhost_detachment():
                    pass
                elif self.player.command_points < s.cp_cost:
                    pass
                elif (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                    pass
                elif not s.can_use(self.player, self.game, phase_name="Fight phase"):
                    pass
                else:
                    game_map = getattr(self.game, "map", None)
                    candidates = []
                    transport_candidates_by_unit = {}
                    seen = set()
                    for unit in list(getattr(self.player.get_army(), "units", []) or []):
                        try:
                            root = unit.get_attached_unit_root()
                        except Exception:
                            raise
                        if root is None:
                            continue
                        try:
                            uid = get_entity_id(root)
                        except Exception:
                            raise
                        if uid in seen:
                            continue
                        seen.add(uid)
                        try:
                            if not root.is_alive():
                                continue
                        except Exception:
                            raise
                        try:
                            if not getattr(root, "deployed", False):
                                continue
                        except Exception:
                            raise
                        try:
                            if getattr(root, "is_in_reserves", lambda: False)():
                                continue
                        except Exception:
                            raise
                        try:
                            if _unit_cannot_be_target_of_stratagem(root):
                                continue
                        except Exception:
                            raise
                        try:
                            if not root.has_any_keyword("ASURYANI"):
                                continue
                        except Exception:
                            raise
                        try:
                            engaged = False
                            for enemy in list(game_map.get_enemy_units(root) or []):
                                if not getattr(enemy, "is_alive", lambda: True)():
                                    continue
                                if not getattr(enemy, "deployed", True):
                                    continue
                                if game_map.is_within_engagement_range(root, enemy):
                                    engaged = True
                                    break
                            if engaged:
                                continue
                        except Exception:
                            raise
                        try:
                            sr = getattr(root, "special_rules", None)
                            owner = str(sr.get("fire_and_fade_no_embark_turn_owner", "") or "") if isinstance(sr, dict) else ""
                            turn = int(sr.get("fire_and_fade_no_embark_turn", 0) or 0) if isinstance(sr, dict) else 0
                            if owner and self.game is not None:
                                if owner == str(getattr(getattr(self.game, "get_current_player", lambda: None)(), "id", "") or ""):
                                    if int(getattr(self.game, "turn", 0) or 0) == int(turn or 0):
                                        continue
                        except Exception:
                            raise
                        transports = self._skyborne_transport_candidates(root)
                        if not transports:
                            continue
                        candidates.append(root)
                        transport_candidates_by_unit[root] = transports
                    if candidates:
                        already = False
                        for r in self._pending_reactions:
                            try:
                                if r.get("event") == "phase_end" and r.get("stratagem") == s.name and r.get("phase") == "Fight phase":
                                    already = True
                                    break
                            except Exception:
                                raise
                        if not already:
                            self._queue_reaction({
                                "event": "phase_end",
                                "phase": "Fight phase",
                                "phase_name": "Fight phase",
                                "stratagem": s.name,
                                "cp_cost": s.cp_cost,
                                "candidates": candidates,
                                "transport_candidates_by_unit": transport_candidates_by_unit,
                            }, use_timer=False)
        except Exception:
            raise
        # Warhost: WEBWAY TUNNEL (end of opponent's Fight phase)
        try:
            is_opponents_turn = player is not self.player
            phase_name = getattr(phase, "name", None)
            if is_opponents_turn and phase_name == "FIGHT_PHASE":
                s = self.get_by_name("WEBWAY TUNNEL")
                if not s:
                    pass
                elif not self._is_warhost_detachment():
                    pass
                elif self.player.command_points < s.cp_cost:
                    pass
                elif (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                    pass
                elif not s.can_use(self.player, self.game, phase_name="Fight phase"):
                    pass
                else:
                    game_map = getattr(self.game, "map", None)
                    candidates = []
                    seen = set()
                    for unit in list(getattr(self.player.get_army(), "units", []) or []):
                        try:
                            root = unit.get_attached_unit_root()
                        except Exception:
                            raise
                        if root is None:
                            continue
                        try:
                            uid = get_entity_id(root)
                        except Exception:
                            raise
                        if uid in seen:
                            continue
                        seen.add(uid)
                        try:
                            if not root.is_alive():
                                continue
                        except Exception:
                            raise
                        try:
                            if not getattr(root, "deployed", False):
                                continue
                        except Exception:
                            raise
                        try:
                            if getattr(root, "is_in_reserves", lambda: False)():
                                continue
                        except Exception:
                            raise
                        try:
                            if _unit_cannot_be_target_of_stratagem(root):
                                continue
                        except Exception:
                            raise
                        try:
                            if not root.has_any_keyword("ASURYANI"):
                                continue
                            if not root.has_keyword("INFANTRY"):
                                continue
                        except Exception:
                            raise
                        try:
                            engaged = False
                            for enemy in list(game_map.get_enemy_units(root) or []):
                                if not getattr(enemy, "is_alive", lambda: True)():
                                    continue
                                if not getattr(enemy, "deployed", True):
                                    continue
                                if game_map.is_within_engagement_range(root, enemy):
                                    engaged = True
                                    break
                            if engaged:
                                continue
                        except Exception:
                            raise
                        if not self._unit_wholly_within_battlefield_edge_distance(root, 9.0):
                            continue
                        candidates.append(root)
                    if candidates:
                        already = False
                        for r in self._pending_reactions:
                            try:
                                if r.get("event") == "phase_end" and r.get("stratagem") == s.name and r.get("phase") == "Fight phase":
                                    already = True
                                    break
                            except Exception:
                                raise
                        if not already:
                            self._queue_reaction({
                                "event": "phase_end",
                                "phase": "Fight phase",
                                "phase_name": "Fight phase",
                                "stratagem": s.name,
                                "cp_cost": s.cp_cost,
                                "candidates": candidates,
                            }, use_timer=False)
        except Exception:
            raise
        # Necrons: ENDLESS SERVITUDE (end of your Fight phase)
        try:
            phase_name = getattr(phase, "name", None)
            if player is self.player and phase_name == "FIGHT_PHASE":
                s = self.get_by_name("ENDLESS SERVITUDE")
                if not s:
                    pass
                elif not self._is_starshatter_arsenal():
                    pass
                elif self.player.command_points < s.cp_cost:
                    pass
                elif (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                    pass
                elif not s.can_use(self.player, self.game, phase_name="Fight phase"):
                    pass
                else:
                    try:
                        army = self.player.get_army()
                    except Exception:
                        raise
                    mgr = self._get_necrons_mgr()
                    game_map = getattr(self.game, "map", None)
                    if game_map is None:
                        return
                    candidates = []
                    seen = set()
                    for unit in list(getattr(army, "units", []) or []):
                        try:
                            root = unit.get_attached_unit_root()
                        except Exception:
                            raise
                        if root is None:
                            continue
                        try:
                            uid = get_entity_id(root)
                        except Exception:
                            raise
                        if uid in seen:
                            continue
                        seen.add(uid)
                        try:
                            if not root.is_alive():
                                continue
                        except Exception:
                            raise
                        try:
                            if not getattr(root, "deployed", False):
                                continue
                        except Exception:
                            raise
                        try:
                            if getattr(root, "is_in_reserves", lambda: False)():
                                continue
                        except Exception:
                            raise
                        try:
                            if _unit_cannot_be_target_of_stratagem(root):
                                continue
                        except Exception:
                            raise
                        if mgr is not None:
                            try:
                                if not mgr.unit_is_necrons(root):
                                    continue
                                if mgr.unit_is_titanic(root):
                                    continue
                            except Exception:
                                raise
                        try:
                            has_rp = getattr(root, "attached_unit_has_reanimation_protocols", None)
                            if callable(has_rp) and not has_rp():
                                continue
                        except Exception:
                            raise
                        in_controlled = False
                        for obj in list(getattr(game_map, "objectives", []) or []):
                            loc = getattr(obj, "location", None)
                            if loc is None or getattr(loc, "removed", False):
                                continue
                            try:
                                if hasattr(loc, "update_control"):
                                    loc.update_control(self.game)
                            except Exception:
                                pass
                            if getattr(loc, "controlling_player", None) is not self.player:
                                continue
                            try:
                                if root.is_within_objective_range(loc):
                                    in_controlled = True
                                    break
                            except Exception:
                                continue
                        if not in_controlled:
                            continue
                        candidates.append(root)
                    if candidates:
                        already = False
                        for r in self._pending_reactions:
                            try:
                                if r.get("event") == "phase_end" and r.get("stratagem") == s.name and r.get("phase") == "Fight phase":
                                    already = True
                                    break
                            except Exception:
                                raise
                        if not already:
                            self._queue_reaction({
                                "event": "phase_end",
                                "phase": "Fight phase",
                                "phase_name": "Fight phase",
                                "stratagem": s.name,
                                "cp_cost": s.cp_cost,
                                "candidates": candidates,
                            }, use_timer=False)
        except Exception:
            raise
        # Queue MURDER-CALL at end of opponent's Fight phase
        try:
            is_opponents_turn = player is not self.player
            phase_name = getattr(phase, "name", None)
            if is_opponents_turn and phase_name == "FIGHT_PHASE":
                s = self.get_by_name("MURDER-CALL")
                if not s:
                    return
                try:
                    army = self.player.get_army()
                except Exception:
                    raise
                we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                    return
                game_map = getattr(self.game, "map", None)
                if game_map is None:
                    return
                candidates = []
                seen = set()
                for unit in list(getattr(army, "units", []) or []):
                    try:
                        root = unit.get_attached_unit_root()
                    except Exception:
                        raise
                    if root is None:
                        continue
                    try:
                        uid = get_entity_id(root)
                    except Exception:
                        raise
                    if uid in seen:
                        continue
                    seen.add(uid)
                    try:
                        if not root.is_alive():
                            continue
                    except Exception:
                        raise
                    try:
                        if getattr(root, "is_in_reserves", lambda: False)():
                            continue
                    except Exception:
                        raise
                    try:
                        if not getattr(root, "deployed", False):
                            continue
                    except Exception:
                        raise
                    try:
                        if not we_mgr.unit_is_blood_legions(root):
                            continue
                    except Exception:
                        raise
                    try:
                        if _unit_cannot_be_target_of_stratagem(root):
                            continue
                    except Exception:
                        raise
                    try:
                        engaged = False
                        for enemy in list(game_map.get_enemy_units(root) or []):
                            if not getattr(enemy, "is_alive", lambda: True)():
                                continue
                            if not getattr(enemy, "deployed", True):
                                continue
                            if game_map.is_within_engagement_range(root, enemy):
                                engaged = True
                                break
                        if engaged:
                            continue
                    except Exception:
                        raise
                    candidates.append(root)
                if not candidates:
                    return
                if not s.can_use(self.player, self.game, phase_name="Fight phase"):
                    return
                for r in self._pending_reactions:
                    try:
                        if r.get("event") == "phase_end" and r.get("stratagem") == s.name and r.get("phase") == "Fight phase":
                            return
                    except Exception:
                        raise
                self._queue_reaction({
                    "event": "phase_end",
                    "phase": "Fight phase",
                    "phase_name": "Fight phase",
                    "stratagem": s.name,
                    "cp_cost": s.cp_cost,
                    "candidates": candidates,
                }, use_timer=False)
        except Exception:
            raise
    def _on_battle_shock_test_started(self, unit, **kwargs):
        # Core: INSANE BRAVERY is used just before taking a Battle-shock test (auto-pass).
        try:
            if unit is None:
                return
            # Only offer when the unit belongs to this player
            try:
                if unit.get_parent_army().player is not self.player:
                    return
            except Exception:
                raise
            try:
                if not bool(getattr(self.game, "battle_shock_step_active", False)):
                    return
            except Exception:
                raise
            # Shadow in the Warp: Insane Bravery cannot be used for these tests.
            try:
                sr = getattr(unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("shadow_in_the_warp_battleshock") is True:
                    return
            except Exception:
                raise
            try:
                if getattr(self.game, "get_current_player", lambda: None)() is not self.player:
                    return
            except Exception:
                raise
            s = self.get_by_name("INSANE BRAVERY")
            if not s:
                return
            # Once per battle restriction
            if self._used_once_per_battle.get("INSANE BRAVERY", False):
                return
            # Timing: Battle-shock step of your Command phase (best-effort via phase tracker)
            if (self._current_phase_name or "").strip().lower() != "command phase":
                return
            if not s.can_use(self.player, self.game, unit=unit, phase_name=self._current_phase_name):
                return
            # Queue as a reaction (UI can choose to use it)
            self._queue_reaction({
                "event": "battle_shock_test_started",
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "unit": unit,
                "phase_name": self._current_phase_name,
            })
        except Exception:
            raise
    def _on_battle_shock_test_resolved(self, unit, passed: bool, **kwargs):
        if not passed and unit and unit.get_parent_army() and unit.get_parent_army().player is self.player:
            try:
                if not bool(getattr(self.game, "battle_shock_step_active", False)):
                    return
            except Exception:
                raise
            try:
                sr = getattr(unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("shadow_in_the_warp_battleshock") is True:
                    return
            except Exception:
                raise
            try:
                if getattr(self.game, "get_current_player", lambda: None)() is not self.player:
                    return
            except Exception:
                raise
            self._last_failed_battle_shock_unit = unit
            # Queue a reaction opportunity for UI: INSANE BRAVERY
            s = self.get_by_name('INSANE BRAVERY')
            if s:
                phase_name = self._current_phase_name
                if s.can_use(self.player, self.game, unit=unit, phase_name=phase_name):
                    self._queue_reaction({
                        'event': 'battle_shock_failed',
                        'stratagem': s.name,
                        'unit': unit,
                        'phase_name': phase_name,
                        'cp_cost': s.cp_cost,
                    })

    # Overwatch triggers: on enemy movement start/end (enqueue for non-active player)
    def _on_unit_move_started(self, unit, action: str, **kwargs):
        self._maybe_queue_overwatch(unit, action, when='start')
        self._maybe_queue_apoplectic_frenzy(unit, action)

    def _on_unit_move_ended(self, unit, action: str, **kwargs):
        self._maybe_queue_overwatch(unit, action, when='end')
        self._maybe_queue_tank_shock(unit, action)
        self._maybe_queue_heroic_intervention(unit, action)
        self._maybe_queue_feigned_retreat(unit, action)
        self._maybe_queue_red_wrath(unit, action)
        self._maybe_queue_cut_down_the_weak(unit, action)

    def _on_unit_shooting_resolved_fire_and_fade(self, attacker_unit=None, **kwargs):
        """
        Reaction window for FIRE AND FADE:
        Your Shooting phase, just after an ASURYANI INFANTRY unit has shot.
        """
        try:
            if attacker_unit is None or self.game is None:
                return
            if (self._current_phase_name or "").strip().lower() != "shooting phase":
                return
            if not self._is_warhost_detachment():
                return
            # Only offer to the active player (your turn)
            active_player = getattr(self.game, "get_current_player", lambda: None)()
            if active_player is not self.player:
                return
            try:
                if attacker_unit.get_parent_army().player is not self.player:
                    return
            except Exception:
                raise
            s = self.get_by_name("FIRE AND FADE")
            if not s:
                return
            if self.player.command_points < s.cp_cost:
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            try:
                root = attacker_unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return
            if _unit_cannot_be_target_of_stratagem(root):
                return
            try:
                if not root.has_any_keyword("ASURYANI"):
                    return
                if not root.has_keyword("INFANTRY"):
                    return
                if root.has_keyword("WRAITH CONSTRUCT"):
                    return
                if root.has_keyword("AIRCRAFT") or bool(getattr(root, "is_aircraft", False)):
                    return
                if str(getattr(root, "name", "") or "").strip().upper() == "ASURMEN":
                    return
            except Exception:
                raise
            if not s.can_use(self.player, self.game, phase_name="Shooting phase", unit=root):
                return
            for r in self._pending_reactions:
                try:
                    if r.get("event") == "unit_shooting_resolved" and r.get("stratagem") == s.name and r.get("unit") is root:
                        return
                except Exception:
                    raise
            self._queue_reaction({
                "event": "unit_shooting_resolved",
                "phase_name": "Shooting phase",
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "unit": root,
                "target_unit": root,
            })
        except Exception:
            raise

    def _on_unit_shooting_resolved_reactive_reposition(self, attacker_unit=None, hits_by_target=None, **_kwargs):
        """
        Reaction window for REACTIVE REPOSITION:
        Opponent's Shooting phase, just after an enemy unit has shot and targeted a Necrons unit.
        """
        try:
            if attacker_unit is None or self.game is None:
                return
            if (self._current_phase_name or "").strip().lower() != "shooting phase":
                return
            active_player = getattr(self.game, "get_current_player", lambda: None)()
            if active_player is self.player:
                return
            if not self._is_starshatter_arsenal():
                return
            s = self.get_by_name("REACTIVE REPOSITION")
            if not s:
                return
            if self.player.command_points < s.cp_cost:
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            mgr = self._get_necrons_mgr()
            targets = []
            atk_key = self._attacker_unit_key(attacker_unit)
            if atk_key:
                targets = list(self._recent_shooting_targets.get(atk_key) or [])
            if not targets and isinstance(hits_by_target, dict):
                targets = list(hits_by_target.keys())
            if atk_key:
                self._recent_shooting_targets.pop(atk_key, None)
            candidates = []
            seen = set()
            for t in list(targets or []):
                try:
                    root = t.get_attached_unit_root()
                except Exception:
                    raise
                if root is None:
                    continue
                try:
                    uid = get_entity_id(root)
                except Exception:
                    raise
                if uid in seen:
                    continue
                seen.add(uid)
                try:
                    if not root.is_alive():
                        continue
                except Exception:
                    raise
                try:
                    if root.get_parent_army().player is not self.player:
                        continue
                except Exception:
                    raise
                try:
                    if not getattr(root, "deployed", False):
                        continue
                except Exception:
                    raise
                try:
                    if _unit_cannot_be_target_of_stratagem(root):
                        continue
                except Exception:
                    raise
                if mgr is not None:
                    try:
                        if not mgr.unit_is_necrons(root):
                            continue
                        if mgr.unit_is_titanic(root):
                            continue
                    except Exception:
                        raise
                candidates.append(root)
            if not candidates:
                return
            for r in self._pending_reactions:
                try:
                    if r.get("event") == "unit_shooting_resolved" and r.get("stratagem") == s.name and r.get("enemy_unit") is attacker_unit:
                        return
                except Exception:
                    raise
            payload = {
                "event": "unit_shooting_resolved",
                "phase_name": "Shooting phase",
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "enemy_unit": attacker_unit,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload)
        except Exception:
            raise
    def _on_unit_shooting_resolved_armour_of_contempt_cleanup(self, attacker_unit=None, **_kwargs) -> None:
        if attacker_unit is None:
            return
        self._clear_armour_of_contempt_for_attacker(attacker_unit)
        self._clear_defensive_effects_for_attacker(attacker_unit)

    def _maybe_queue_tank_shock(self, charging_unit, action: str) -> None:
        # Trigger condition: just after a VEHICLE unit from your army ends a Charge move.
        try:
            if str(action or "").strip().lower() != "charge":
                return
            if charging_unit is None or not getattr(charging_unit, "is_alive", lambda: True)():
                return
            # Must be your unit
            owner_player = charging_unit.get_parent_army().player
            if owner_player is not self.player:
                return
            # Must be Charge phase and your turn (best-effort; phase gate is also enforced at use-time)
            if (self._current_phase_name or "").strip().lower() != "charge phase":
                return
            if not bool(getattr(charging_unit, "is_vehicle", False)):
                return
        except Exception:
            raise
        s = self.get_by_name("TANK SHOCK")
        if not s:
            return
        if self.player.command_points < s.cp_cost:
            return

        # Must have at least one enemy unit within Engagement Range
        enemy_units = []
        try:
            enemy_units = list(self.game.map.get_enemy_units(charging_unit)) if self.game and getattr(self.game, "map", None) else []
        except Exception:
            raise
        eligible = []
        for e in enemy_units:
            try:
                if e is None or not e.is_alive():
                    continue
                if self.game and getattr(self.game, "map", None) and self.game.map.is_within_engagement_range(charging_unit, e):
                    eligible.append(e)
            except Exception:
                raise
        if not eligible:
            return

        # Queue reaction: UI can choose enemy_unit later; default heuristic will pick the first.
        self._queue_reaction({
            "event": "charge_move_ended",
            "phase_name": "Charge phase",
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "unit": charging_unit,
            "target_unit": charging_unit,
            "eligible_enemy_units": eligible,
        })

    def _maybe_queue_heroic_intervention(self, charging_unit, action: str) -> None:
        # Trigger condition: after an enemy unit ends a Charge move (opponent's turn).
        try:
            if str(action or "").strip().lower() != "charge":
                return
            if charging_unit is None or not getattr(charging_unit, "is_alive", lambda: True)():
                return
            owner_player = charging_unit.get_parent_army().player
            if owner_player is self.player:
                return
            if (self._current_phase_name or "").strip().lower() != "charge phase":
                return
        except Exception:
            raise
        s = self.get_by_name("HEROIC INTERVENTION")
        if not s:
            return

        # Find eligible friendly units within 6" that could charge that enemy unit.
        candidates = []
        try:
            for unit in list(getattr(self.player.get_army(), "units", []) or []):
                if not unit.is_alive() or not unit.deployed:
                    continue
                # Restriction: only WALKER vehicles can be selected.
                try:
                    if unit.has_keyword("Vehicle") and not unit.has_keyword("Walker"):
                        continue
                except Exception:
                    raise
                # Core rule: battle-shocked or embarked units cannot be targeted.
                if _unit_cannot_be_target_of_stratagem(unit):
                    continue
                dist = None
                try:
                    if self.game and getattr(self.game, "map", None):
                        dist = self.game.map.get_distance_between_units(unit, charging_unit)
                except Exception:
                    raise
                if dist is None or dist > 6.0:
                    continue
                try:
                    if not unit.can_declare_charge_against(charging_unit, self.game, out_of_turn=True):
                        continue
                except Exception:
                    raise
                eff_cost = s.cp_cost
                try:
                    if hasattr(self.player, "preview_stratagem_cp_cost"):
                        eff_cost = int(self.player.preview_stratagem_cp_cost(s, target_unit=unit).get("cost", s.cp_cost))
                except Exception:
                    raise
                if self.player.command_points < eff_cost:
                    continue
                candidates.append(unit)
        except Exception:
            raise
        if not candidates:
            return

        # Deduplicate for the same enemy unit.
        already = False
        for r in self._pending_reactions:
            if r.get("event") == "heroic_intervention" and r.get("stratagem") == s.name and r.get("enemy_unit") is charging_unit:
                already = True
                break
        if already:
            return

        self._queue_reaction({
            "event": "heroic_intervention",
            "phase_name": "Charge phase",
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "enemy_unit": charging_unit,
            "candidates": candidates,
        })

    def _on_shooting_targets_selected(self, attacking_unit=None, target_units=None, **kwargs):
        """
        Reaction window for GO TO GROUND:
        Opponent Shooting phase, just after an enemy unit has selected its targets.
        """
        try:
            if not self.game or not getattr(self.game, "map", None):
                return
            if (self._current_phase_name or "").strip().lower() != "shooting phase":
                return
            # This event is published by the active shooter's execution; we offer to the NON-active player.
            if attacking_unit is None:
                return
            owner_player = attacking_unit.get_parent_army().player
            if owner_player is self.player:
                return  # only opponent can react
        except Exception:
            raise
        try:
            atk_key = self._attacker_unit_key(attacking_unit)
            if atk_key:
                self._recent_shooting_targets[atk_key] = list(target_units or [])
        except Exception:
            raise
        # GO TO GROUND
        try:
            s = self.get_by_name("GO TO GROUND")
            if s and self.player.command_points >= s.cp_cost:
                candidates = []
                for u in list(target_units or []):
                    try:
                        if u is None or not u.is_alive():
                            continue
                        if u.get_parent_army().player is not self.player:
                            continue
                        if not bool(getattr(u, "is_infantry", False)):
                            continue
                        if _unit_cannot_be_target_of_stratagem(u):
                            continue
                        candidates.append(u)
                    except Exception:
                        raise
                if candidates:
                    # Queue as a reaction with candidates; UI may choose which unit to protect.
                    self._queue_reaction({
                        "event": "shooting_targets_selected",
                        "phase_name": "Shooting phase",
                        "stratagem": s.name,
                        "cp_cost": s.cp_cost,
                        "attacking_unit": attacking_unit,
                        "candidates": candidates,
                    })
        except Exception:
            raise
        # Also offer SMOKESCREEN in the same window (opponent Shooting phase, after targets selected).
        try:
            s2 = self.get_by_name("SMOKESCREEN")
            can_offer = bool(
                s2
                and self.player.command_points >= s2.cp_cost
                and (s2.name or "").strip().upper() not in self._used_stratagems_this_phase
            )
            if can_offer:
                smoke_candidates = []
                for u in list(target_units or []):
                    try:
                        if u is None or not u.is_alive():
                            continue
                        if u.get_parent_army().player is not self.player:
                            continue
                        if _unit_cannot_be_target_of_stratagem(u):
                            continue
                        # Target must be a SMOKE unit
                        if hasattr(u, "has_keyword") and callable(getattr(u, "has_keyword")):
                            if not u.has_keyword("SMOKE"):
                                continue
                        else:
                            continue
                        smoke_candidates.append(u)
                    except Exception:
                        raise
                if smoke_candidates:
                    self._queue_reaction({
                        "event": "shooting_targets_selected",
                        "phase_name": "Shooting phase",
                        "stratagem": s2.name,
                        "cp_cost": s2.cp_cost,
                        "attacking_unit": attacking_unit,
                        "candidates": smoke_candidates,
                    })
        except Exception:
            raise
        # ARMOUR OF CONTEMPT / THE FOE FORESEEN (opponent Shooting phase, after targets selected).
        try:
            for strat_name in ("ARMOUR OF CONTEMPT", "THE FOE FORESEEN"):
                s4 = self.get_by_name(strat_name)
                if not s4:
                    continue
                if self.player.command_points < s4.cp_cost:
                    continue
                if (s4.name or "").strip().upper() in self._used_stratagems_this_phase:
                    continue
                candidates = []
                for u in list(target_units or []):
                    try:
                        if u is None or not u.is_alive():
                            continue
                        if u.get_parent_army().player is not self.player:
                            continue
                        if _unit_cannot_be_target_of_stratagem(u):
                            continue
                        if not u.has_any_keyword("ADEPTUS ASTARTES"):
                            continue
                        candidates.append(u)
                    except Exception:
                        raise
                if not candidates:
                    continue
                already = False
                for r in self._pending_reactions:
                    try:
                        if r.get("event") == "shooting_targets_selected" and r.get("stratagem") == s4.name and r.get("attacking_unit") is attacking_unit:
                            already = True
                            break
                    except Exception:
                        raise
                if already:
                    continue
                self._queue_reaction({
                    "event": "shooting_targets_selected",
                    "phase_name": "Shooting phase",
                    "stratagem": s4.name,
                    "cp_cost": s4.cp_cost,
                    "attacking_unit": attacking_unit,
                    "candidates": candidates,
                })
        except Exception:
            raise
        # Khorne Daemonkin: BLESSING OF BURNING BLOOD (opponent Shooting phase, after targets selected).
        try:
            s5 = self.get_by_name("BLESSING OF BURNING BLOOD")
            if s5 and self.player.command_points >= s5.cp_cost and (s5.name or "").strip().upper() not in self._used_stratagems_this_phase:
                try:
                    army = self.player.get_army()
                except Exception:
                    raise
                we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                if we_mgr is not None and getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                    game_map = getattr(self.game, "map", None)
                    if game_map is not None:
                        for we_unit in list(target_units or []):
                            try:
                                if we_unit is None or not we_unit.is_alive():
                                    continue
                                if we_unit.get_parent_army().player is not self.player:
                                    continue
                                if _unit_cannot_be_target_of_stratagem(we_unit):
                                    continue
                                if not we_mgr.unit_is_world_eaters(we_unit):
                                    continue
                            except Exception:
                                raise
                            candidates = []
                            seen = set()
                            for bl_unit in list(getattr(army, "units", []) or []):
                                try:
                                    root = bl_unit.get_attached_unit_root()
                                except Exception:
                                    raise
                                if root is None:
                                    continue
                                try:
                                    uid = get_entity_id(root)
                                except Exception:
                                    raise
                                if uid in seen:
                                    continue
                                seen.add(uid)
                                try:
                                    if not root.is_alive():
                                        continue
                                except Exception:
                                    raise
                                try:
                                    if not getattr(root, "deployed", False):
                                        continue
                                except Exception:
                                    raise
                                try:
                                    if getattr(root, "is_in_reserves", lambda: False)():
                                        continue
                                except Exception:
                                    raise
                                try:
                                    if _unit_cannot_be_target_of_stratagem(root):
                                        continue
                                except Exception:
                                    raise
                                try:
                                    if not we_mgr.unit_is_blood_legions(root):
                                        continue
                                except Exception:
                                    raise
                                try:
                                    dist = game_map.get_distance_between_units(root, we_unit)
                                except Exception:
                                    raise
                                if dist is None or dist > 6.0:
                                    continue
                                candidates.append(root)
                            if not candidates:
                                continue
                            already = False
                            for r in self._pending_reactions:
                                try:
                                    if (
                                        r.get("event") == "shooting_targets_selected"
                                        and r.get("stratagem") == s5.name
                                        and r.get("attacking_unit") is attacking_unit
                                        and r.get("world_eaters_unit") is we_unit
                                    ):
                                        already = True
                                        break
                                except Exception:
                                    raise
                            if already:
                                continue
                            payload = {
                                "event": "shooting_targets_selected",
                                "phase_name": "Shooting phase",
                                "stratagem": s5.name,
                                "cp_cost": s5.cp_cost,
                                "attacking_unit": attacking_unit,
                                "world_eaters_unit": we_unit,
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload)
        except Exception:
            raise
        # Necrons: UNYIELDING FORMS (opponent Shooting phase, after targets selected).
        try:
            s6 = self.get_by_name("UNYIELDING FORMS")
            if s6 and self._is_starshatter_arsenal():
                if self.player.command_points < s6.cp_cost:
                    pass
                elif (s6.name or "").strip().upper() in self._used_stratagems_this_phase:
                    pass
                else:
                    mgr = self._get_necrons_mgr()
                    candidates = []
                    seen = set()
                    for u in list(target_units or []):
                        try:
                            root = u.get_attached_unit_root()
                        except Exception:
                            raise
                        if root is None:
                            continue
                        try:
                            uid = get_entity_id(root)
                        except Exception:
                            raise
                        if uid in seen:
                            continue
                        seen.add(uid)
                        try:
                            if not root.is_alive():
                                continue
                        except Exception:
                            raise
                        try:
                            if root.get_parent_army().player is not self.player:
                                continue
                        except Exception:
                            raise
                        try:
                            if _unit_cannot_be_target_of_stratagem(root):
                                continue
                        except Exception:
                            raise
                        if mgr is not None:
                            try:
                                if not mgr.unit_is_necrons(root):
                                    continue
                                if mgr.unit_is_titanic(root):
                                    continue
                                if not mgr.unit_is_vehicle_or_mounted(root):
                                    continue
                            except Exception:
                                raise
                        candidates.append(root)
                    if candidates:
                        already = False
                        for r in self._pending_reactions:
                            try:
                                if r.get("event") == "shooting_targets_selected" and r.get("stratagem") == s6.name and r.get("attacking_unit") is attacking_unit:
                                    already = True
                                    break
                            except Exception:
                                raise
                        if not already:
                            payload = {
                                "event": "shooting_targets_selected",
                                "phase_name": "Shooting phase",
                                "stratagem": s6.name,
                                "cp_cost": s6.cp_cost,
                                "attacking_unit": attacking_unit,
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload)
        except Exception:
            raise
        # Generic defensive reactions (after targets selected).
        try:
            self._queue_generic_defensive_reactions(
                attacking_unit,
                list(target_units or []),
                phase_name="Shooting phase",
            )
        except Exception:
            raise
        # Warhost: LIGHTNING-FAST REACTIONS (opponent Shooting phase, after targets selected).
        try:
            s3 = self.get_by_name("LIGHTNING-FAST REACTIONS")
            if not s3:
                return
            if not self._is_warhost_detachment():
                return
            if self.player.command_points < s3.cp_cost:
                return
            if (s3.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            candidates = []
            for u in list(target_units or []):
                try:
                    if u is None or not u.is_alive():
                        continue
                    if u.get_parent_army().player is not self.player:
                        continue
                    if _unit_cannot_be_target_of_stratagem(u):
                        continue
                    if not u.has_any_keyword("ASURYANI"):
                        continue
                    if u.has_keyword("WRAITH CONSTRUCT"):
                        continue
                    candidates.append(u)
                except Exception:
                    raise
            if not candidates:
                return
            self._queue_reaction({
                "event": "shooting_targets_selected",
                "phase_name": "Shooting phase",
                "stratagem": s3.name,
                "cp_cost": s3.cp_cost,
                "attacking_unit": attacking_unit,
                "candidates": candidates,
            })
        except Exception:
            raise
    def _on_blood_surge_triggered(self, player=None, unit=None, attacker_unit=None, **kwargs):
        """
        Reaction window for BERZERKER'S WRATH:
        Opponent Shooting phase, just after an enemy unit has shot and a BERZERKERS unit can Blood Surge.
        """
        try:
            if player is not self.player:
                return
            if unit is None or attacker_unit is None:
                return
            if (self._current_phase_name or "").strip().lower() != "shooting phase":
                return
            s = self.get_by_name("BERZERKER\u2019S WRATH") or self.get_by_name("BERZERKER'S WRATH")
            if not s:
                return
            if self.player.command_points < s.cp_cost:
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_berzerker_warband", lambda: False)():
                return
            try:
                if not (unit.has_keyword("KHORNE") and unit.has_keyword("BERZERKERS")):
                    return
            except Exception:
                raise
            if _unit_cannot_be_target_of_stratagem(unit):
                return
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is self.player:
                return
            try:
                if not unit.can_blood_surge(game=self.game, game_map=getattr(self.game, "map", None)):
                    return
            except Exception:
                raise
            phase_name = kwargs.get("phase_name") or self._current_phase_name or "Shooting phase"
            phase_name = str(phase_name or "").replace("_", " ").title()
            if not s.can_use(self.player, self.game, target_unit=unit, attacker_unit=attacker_unit, phase_name=phase_name):
                return
            for r in self._pending_reactions:
                try:
                    if r.get("event") == "blood_surge_triggered" and r.get("stratagem") == s.name and r.get("unit") is unit and r.get("attacker_unit") is attacker_unit:
                        return
                except Exception:
                    raise
            self._queue_reaction({
                "event": "blood_surge_triggered",
                "phase_name": phase_name,
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "unit": unit,
                "target_unit": unit,
                "attacker_unit": attacker_unit,
            })
        except Exception:
            raise
    def _on_fight_unit_selected(self, unit=None, selecting_player=None, **kwargs):
        """
        Reaction window for EPIC CHALLENGE:
        Fight phase, when a CHARACTER unit from your army that is within Engagement Range of one or more
        Attached units is selected to fight.
        """
        try:
            if unit is None:
                return
            if (self._current_phase_name or "").strip().lower() != "fight phase":
                return
            # Offer only to the player selecting the unit
            if selecting_player is not self.player:
                return
            s = self.get_by_name("EPIC CHALLENGE")
            if not s:
                return
            if self.player.command_points < s.cp_cost:
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            # Must be a CHARACTER unit
            if not bool(getattr(unit, "is_character", False)) and not (hasattr(unit, "has_keyword") and unit.has_keyword("CHARACTER")):
                return
            # Must be within ER of one or more enemy Attached units
            try:
                enemy_units = self.game.map.get_enemy_units(unit)
            except Exception:
                raise
            ok = False
            for e in list(enemy_units or []):
                try:
                    if not e.is_alive():
                        continue
                    if not self.game.map.is_within_engagement_range(unit, e):
                        continue
                    members = []
                    try:
                        fn = getattr(e, "get_attached_unit_members", None)
                        if callable(fn):
                            members = list(fn())
                    except Exception:
                        raise
                    if len(members) > 1:
                        ok = True
                        break
                except Exception:
                    raise
            if not ok:
                return
            # Eligible models: CHARACTER models in your unit (include attached leaders).
            try:
                fn = getattr(unit, "get_attached_unit_models", None)
                candidates = list(fn() or []) if callable(fn) else list(getattr(unit, "models", []) or [])
            except Exception:
                raise
            models = []
            for m in list(candidates or []):
                try:
                    if not getattr(m, "is_alive", True):
                        continue
                    if bool(getattr(m, "is_character", False)):
                        models.append(m)
                        continue
                    pu = getattr(m, "parent_unit", None)
                    if pu is None:
                        continue
                    fn = getattr(pu, "has_keyword_local", None)
                    if callable(fn):
                        if bool(fn("Character")):
                            models.append(m)
                        continue
                    if not hasattr(pu, "keywords"):
                        if bool(getattr(pu, "is_character", False)):
                            models.append(m)
                        continue
                    kws = getattr(pu, "keywords", []) or []
                    if "character" in [str(k).lower() for k in kws]:
                        models.append(m)
                except Exception:
                    raise
            if not models:
                return
            self._queue_reaction({
                "event": "fight_unit_selected",
                "phase_name": "Fight phase",
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "unit": unit,
                "eligible_models": models,
            })
        except Exception:
            raise
    def _on_fight_targets_selected(self, attacking_unit=None, target_units=None, **kwargs):
        """
        Reaction windows for FRENZIED RESILIENCE and LIGHTNING-FAST REACTIONS:
        Fight phase, just after an enemy unit has selected its targets.
        """
        if attacking_unit is None:
            return
        if (self._current_phase_name or "").strip().lower() != "fight phase":
            return
        try:
            owner_player = attacking_unit.get_parent_army().player
        except Exception:
            raise
        if owner_player is None or owner_player is self.player:
            return

        # FRENZIED RESILIENCE (World Eaters)
        try:
            s = self.get_by_name("FRENZIED RESILIENCE")
            if s and self.player.command_points >= s.cp_cost and (s.name or "").strip().upper() not in self._used_stratagems_this_phase:
                try:
                    army = self.player.get_army()
                except Exception:
                    raise
                we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                if we_mgr is not None and getattr(we_mgr, "is_berzerker_warband", lambda: False)():
                    candidates = []
                    for unit in list(target_units or []):
                        try:
                            if unit is None or not unit.is_alive():
                                continue
                            if unit.get_parent_army().player is not self.player:
                                continue
                            if _unit_cannot_be_target_of_stratagem(unit):
                                continue
                            if not (hasattr(unit, "has_any_keyword") and unit.has_any_keyword("WORLD EATERS")):
                                continue
                            candidates.append(unit)
                        except Exception:
                            raise
                    if candidates:
                        for r in self._pending_reactions:
                            try:
                                if r.get("event") == "fight_targets_selected" and r.get("stratagem") == s.name and r.get("attacking_unit") is attacking_unit:
                                    candidates = []
                                    break
                            except Exception:
                                raise
                        if candidates:
                            payload = {
                                "event": "fight_targets_selected",
                                "phase_name": "Fight phase",
                                "stratagem": s.name,
                                "cp_cost": s.cp_cost,
                                "attacking_unit": attacking_unit,
                                "target_units": list(target_units or []),
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload)
        except Exception:
            raise
        # Rage-cursed Onslaught: DEATHLESS DUTY
        try:
            s = self.get_by_name("DEATHLESS DUTY")
            if s and self.player.command_points >= s.cp_cost and (s.name or "").strip().upper() not in self._used_stratagems_this_phase:
                try:
                    army = self.player.get_army()
                except Exception:
                    raise
                sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
                if sm_mgr is not None and getattr(sm_mgr, "is_rage_cursed_onslaught", lambda: False)():
                    candidates = []
                    for unit in list(target_units or []):
                        try:
                            if unit is None or not unit.is_alive():
                                continue
                            if unit.get_parent_army().player is not self.player:
                                continue
                            if _unit_cannot_be_target_of_stratagem(unit):
                                continue
                            if not unit.has_any_keyword("DEATH COMPANY"):
                                continue
                            candidates.append(unit)
                        except Exception:
                            raise
                    if candidates:
                        already = False
                        for r in self._pending_reactions:
                            try:
                                if r.get("event") == "fight_targets_selected" and r.get("stratagem") == s.name and r.get("attacking_unit") is attacking_unit:
                                    already = True
                                    break
                            except Exception:
                                raise
                        if not already:
                            payload = {
                                "event": "fight_targets_selected",
                                "phase_name": "Fight phase",
                                "stratagem": s.name,
                                "cp_cost": s.cp_cost,
                                "attacking_unit": attacking_unit,
                                "target_units": list(target_units or []),
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload)
        except Exception:
            raise
        # EMPEROR'S CHILDREN: DEATH ECSTASY
        try:
            s = self.get_by_name("DEATH ECSTASY")
            if s and self.player.command_points >= s.cp_cost and (s.name or "").strip().upper() not in self._used_stratagems_this_phase:
                try:
                    army = self.player.get_army()
                except Exception:
                    raise
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is not None and getattr(mgr, "is_peerless_bladesmen", lambda: False)():
                    candidates = []
                    for unit in list(target_units or []):
                        try:
                            if unit is None or not unit.is_alive():
                                continue
                            if unit.get_parent_army().player is not self.player:
                                continue
                            if _unit_cannot_be_target_of_stratagem(unit):
                                continue
                            if not mgr.is_emperors_children_unit(unit):
                                continue
                            candidates.append(unit)
                        except Exception:
                            raise
                    if candidates:
                        already = False
                        for r in self._pending_reactions:
                            try:
                                if r.get("event") == "fight_targets_selected" and r.get("stratagem") == s.name and r.get("attacking_unit") is attacking_unit:
                                    already = True
                                    break
                            except Exception:
                                raise
                        if not already:
                            payload = {
                                "event": "fight_targets_selected",
                                "phase_name": "Fight phase",
                                "stratagem": s.name,
                                "cp_cost": s.cp_cost,
                                "attacking_unit": attacking_unit,
                                "target_units": list(target_units or []),
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload)
        except Exception:
            raise
        # ARMOUR OF CONTEMPT / THE FOE FORESEEN (opponent Fight phase, after targets selected).
        try:
            for strat_name in ("ARMOUR OF CONTEMPT", "THE FOE FORESEEN"):
                s4 = self.get_by_name(strat_name)
                if not s4:
                    continue
                if self.player.command_points < s4.cp_cost:
                    continue
                if (s4.name or "").strip().upper() in self._used_stratagems_this_phase:
                    continue
                candidates = []
                for unit in list(target_units or []):
                    try:
                        if unit is None or not unit.is_alive():
                            continue
                        if unit.get_parent_army().player is not self.player:
                            continue
                        if _unit_cannot_be_target_of_stratagem(unit):
                            continue
                        if not unit.has_any_keyword("ADEPTUS ASTARTES"):
                            continue
                        candidates.append(unit)
                    except Exception:
                        raise
                if not candidates:
                    continue
                already = False
                for r in self._pending_reactions:
                    try:
                        if r.get("event") == "fight_targets_selected" and r.get("stratagem") == s4.name and r.get("attacking_unit") is attacking_unit:
                            already = True
                            break
                    except Exception:
                        raise
                if already:
                    continue
                self._queue_reaction({
                    "event": "fight_targets_selected",
                    "phase_name": "Fight phase",
                    "stratagem": s4.name,
                    "cp_cost": s4.cp_cost,
                    "attacking_unit": attacking_unit,
                    "candidates": candidates,
                })
        except Exception:
            raise
        # Necrons: UNYIELDING FORMS (Fight phase, after targets selected).
        try:
            s6 = self.get_by_name("UNYIELDING FORMS")
            if s6 and self._is_starshatter_arsenal():
                if self.player.command_points < s6.cp_cost:
                    pass
                elif (s6.name or "").strip().upper() in self._used_stratagems_this_phase:
                    pass
                else:
                    mgr = self._get_necrons_mgr()
                    candidates = []
                    seen = set()
                    for u in list(target_units or []):
                        try:
                            root = u.get_attached_unit_root()
                        except Exception:
                            raise
                        if root is None:
                            continue
                        try:
                            uid = get_entity_id(root)
                        except Exception:
                            raise
                        if uid in seen:
                            continue
                        seen.add(uid)
                        try:
                            if not root.is_alive():
                                continue
                        except Exception:
                            raise
                        try:
                            if root.get_parent_army().player is not self.player:
                                continue
                        except Exception:
                            raise
                        try:
                            if _unit_cannot_be_target_of_stratagem(root):
                                continue
                        except Exception:
                            raise
                        if mgr is not None:
                            try:
                                if not mgr.unit_is_necrons(root):
                                    continue
                                if mgr.unit_is_titanic(root):
                                    continue
                                if not mgr.unit_is_vehicle_or_mounted(root):
                                    continue
                            except Exception:
                                raise
                        candidates.append(root)
                    if candidates:
                        already = False
                        for r in self._pending_reactions:
                            try:
                                if r.get("event") == "fight_targets_selected" and r.get("stratagem") == s6.name and r.get("attacking_unit") is attacking_unit:
                                    already = True
                                    break
                            except Exception:
                                raise
                        if not already:
                            payload = {
                                "event": "fight_targets_selected",
                                "phase_name": "Fight phase",
                                "stratagem": s6.name,
                                "cp_cost": s6.cp_cost,
                                "attacking_unit": attacking_unit,
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload)
        except Exception:
            raise
        # Khorne Daemonkin: BLESSING OF BURNING BLOOD (opponent Fight phase, after targets selected).
        try:
            s5 = self.get_by_name("BLESSING OF BURNING BLOOD")
            if s5 and self.player.command_points >= s5.cp_cost and (s5.name or "").strip().upper() not in self._used_stratagems_this_phase:
                try:
                    army = self.player.get_army()
                except Exception:
                    raise
                we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                if we_mgr is not None and getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                    game_map = getattr(self.game, "map", None)
                    if game_map is not None:
                        for we_unit in list(target_units or []):
                            try:
                                if we_unit is None or not we_unit.is_alive():
                                    continue
                                if we_unit.get_parent_army().player is not self.player:
                                    continue
                                if _unit_cannot_be_target_of_stratagem(we_unit):
                                    continue
                                if not we_mgr.unit_is_world_eaters(we_unit):
                                    continue
                            except Exception:
                                raise
                            candidates = []
                            seen = set()
                            for bl_unit in list(getattr(army, "units", []) or []):
                                try:
                                    root = bl_unit.get_attached_unit_root()
                                except Exception:
                                    raise
                                if root is None:
                                    continue
                                try:
                                    uid = get_entity_id(root)
                                except Exception:
                                    raise
                                if uid in seen:
                                    continue
                                seen.add(uid)
                                try:
                                    if not root.is_alive():
                                        continue
                                except Exception:
                                    raise
                                try:
                                    if not getattr(root, "deployed", False):
                                        continue
                                except Exception:
                                    raise
                                try:
                                    if getattr(root, "is_in_reserves", lambda: False)():
                                        continue
                                except Exception:
                                    raise
                                try:
                                    if _unit_cannot_be_target_of_stratagem(root):
                                        continue
                                except Exception:
                                    raise
                                try:
                                    if not we_mgr.unit_is_blood_legions(root):
                                        continue
                                except Exception:
                                    raise
                                try:
                                    dist = game_map.get_distance_between_units(root, we_unit)
                                except Exception:
                                    raise
                                if dist is None or dist > 6.0:
                                    continue
                                candidates.append(root)
                            if not candidates:
                                continue
                            already = False
                            for r in self._pending_reactions:
                                try:
                                    if (
                                        r.get("event") == "fight_targets_selected"
                                        and r.get("stratagem") == s5.name
                                        and r.get("attacking_unit") is attacking_unit
                                        and r.get("world_eaters_unit") is we_unit
                                    ):
                                        already = True
                                        break
                                except Exception:
                                    raise
                            if already:
                                continue
                            payload = {
                                "event": "fight_targets_selected",
                                "phase_name": "Fight phase",
                                "stratagem": s5.name,
                                "cp_cost": s5.cp_cost,
                                "attacking_unit": attacking_unit,
                                "world_eaters_unit": we_unit,
                                "candidates": candidates,
                            }
                            if len(candidates) == 1:
                                payload["target_unit"] = candidates[0]
                            self._queue_reaction(payload)
        except Exception:
            raise
        # Generic defensive reactions (after targets selected).
        try:
            self._queue_generic_defensive_reactions(
                attacking_unit,
                list(target_units or []),
                phase_name="Fight phase",
            )
        except Exception:
            raise
        # Warhost: LIGHTNING-FAST REACTIONS (Fight phase)
        try:
            s = self.get_by_name("LIGHTNING-FAST REACTIONS")
            if not s:
                return
            if not self._is_warhost_detachment():
                return
            if self.player.command_points < s.cp_cost:
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            candidates = []
            for unit in list(target_units or []):
                try:
                    if unit is None or not unit.is_alive():
                        continue
                    if unit.get_parent_army().player is not self.player:
                        continue
                    if _unit_cannot_be_target_of_stratagem(unit):
                        continue
                    if not unit.has_any_keyword("ASURYANI"):
                        continue
                    if unit.has_keyword("WRAITH CONSTRUCT"):
                        continue
                    candidates.append(unit)
                except Exception:
                    raise
            if not candidates:
                return
            self._queue_reaction({
                "event": "fight_targets_selected",
                "phase_name": "Fight phase",
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "attacking_unit": attacking_unit,
                "candidates": candidates,
            })
        except Exception:
            raise
    def _on_fight_sequence_complete(self, unit=None, player=None, stage=None, **kwargs):
        """
        Reaction window for COUNTER-OFFENSIVE:
        Fight phase, just after an enemy unit has fought.
        """
        try:
            if unit is None or not self.game:
                return
            if (self._current_phase_name or "").strip().lower() != "fight phase":
                return
            # Offer only to the opponent of the unit that just fought
            owner_player = None
            try:
                owner_player = unit.get_parent_army().player
            except Exception:
                raise
            if owner_player is None or owner_player is self.player:
                return
            s = self.get_by_name("COUNTER-OFFENSIVE")
            if not s:
                return
            if self.player.command_points < s.cp_cost:
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            # Avoid duplicate pending entries
            for r in self._pending_reactions:
                if str(r.get("stratagem", "")).strip().upper() == "COUNTER-OFFENSIVE":
                    return
            # Build eligible candidates (any unit that can fight and has not fought)
            try:
                if hasattr(self.game, "get_eligible_fighting_units"):
                    base_units = list(self.game.get_eligible_fighting_units(self.player))
                else:
                    base_units = list(getattr(self.player.get_army(), "units", []) or [])
            except Exception:
                raise
            fight_mgr = getattr(self.game, "fight_phase_manager", None)
            try:
                fought = set(getattr(fight_mgr, "fought_units", set()) or []) if fight_mgr else set()
            except Exception:
                raise
            canonicalize = getattr(fight_mgr, "_canonical_unit_for_fight", None) if fight_mgr else None
            candidates = []
            seen = set()
            for u in list(base_units or []):
                try:
                    root = canonicalize(u) if callable(canonicalize) else u
                except Exception:
                    raise
                if root is None:
                    continue
                rid = get_entity_id(root)
                if rid in seen:
                    continue
                seen.add(rid)
                try:
                    if root in fought:
                        continue
                except Exception:
                    raise
                try:
                    if getattr(root, "round_state", None) and getattr(root.round_state, "fought_this_phase", False):
                        continue
                except Exception:
                    raise
                try:
                    if _unit_cannot_be_target_of_stratagem(root):
                        continue
                except Exception:
                    raise
                try:
                    if root.get_parent_army().player is not self.player:
                        continue
                except Exception:
                    raise
                try:
                    if hasattr(root, "is_eligible_to_fight") and callable(root.is_eligible_to_fight):
                        if not root.is_eligible_to_fight(self.game.map):
                            continue
                except Exception:
                    raise
                candidates.append(root)
            if not candidates:
                return
            self._queue_reaction({
                "event": "fight_sequence_complete",
                "phase_name": "Fight phase",
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "enemy_unit": unit,
                "stage": stage,
                "candidates": candidates,
            })
        except Exception:
            raise
    def _on_fight_attacks_resolved(self, unit=None, target_unit=None, **_kwargs) -> None:
        """
        Reaction window for A WORTHY SKULL:
        Fight phase, just after a unit has fought and destroyed a CHARACTER/MONSTER model.
        """
        try:
            if unit is None or not self.game:
                return
            if (self._current_phase_name or "").strip().lower() != "fight phase":
                return
            s = self.get_by_name("A WORTHY SKULL")
            if not s:
                return
            try:
                if unit.get_parent_army().player is not self.player:
                    return
            except Exception:
                raise
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if not self._worthy_skull_kills.get(root, False):
                return
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    return
            except Exception:
                raise
            try:
                army = root.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                return
            try:
                if not we_mgr.unit_is_blood_tithe_eligible(root):
                    return
            except Exception:
                raise
            if not s.can_use(self.player, self.game, unit=root, phase_name=self._current_phase_name):
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            for r in self._pending_reactions:
                if r.get("event") == "fight_attacks_resolved" and r.get("stratagem") == s.name and r.get("unit") is root:
                    return
            self._queue_reaction({
                "event": "fight_attacks_resolved",
                "phase_name": "Fight phase",
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "unit": root,
                "target_unit": target_unit,
            })
        except Exception:
            raise
        finally:
            try:
                if unit is not None:
                    root = unit.get_attached_unit_root()
                else:
                    root = None
            except Exception:
                raise
            if root is not None:
                try:
                    self._worthy_skull_kills.pop(root, None)
                except Exception:
                    raise
    def _on_fight_attacks_resolved_consolidate_stratagems(self, unit=None, target_unit=None, **_kwargs) -> None:
        """
        Reaction window for consolidate-extension stratagems:
        Fight phase, just before a unit Consolidates.
        """
        try:
            if unit is None or not self.game:
                return
            if (self._current_phase_name or "").strip().lower() != "fight phase":
                return
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return
            try:
                if not root.is_alive():
                    return
            except Exception:
                raise
            try:
                if root.get_parent_army().player is not self.player:
                    return
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    return
            except Exception:
                raise
            phase_name = self._current_phase_name or "Fight phase"
            for s in list(self.available or []):
                spec = self._get_consolidate_move_spec(s)
                if not spec:
                    continue
                if "fight" not in set(spec.get("phases") or []):
                    continue
                if not self._unit_matches_defensive_target_spec(root, spec):
                    continue
                if bool(spec.get("requires_engagement", False)):
                    try:
                        max_dist = float(spec.get("max_distance", 0) or 0)
                    except Exception:
                        max_dist = 0.0
                    if max_dist > 0 and not self._consolidate_requires_engagement_possible(root, max_dist):
                        continue
                if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                    continue
                if not s.can_use(self.player, self.game, target_unit=root, phase_name=phase_name):
                    continue
                already = False
                for r in self._pending_reactions:
                    try:
                        if r.get("event") == "before_consolidate" and r.get("stratagem") == s.name and r.get("unit") is root:
                            already = True
                            break
                    except Exception:
                        raise
                if already:
                    continue
                payload = {
                    "event": "before_consolidate",
                    "phase_name": phase_name,
                    "stratagem": s.name,
                    "cp_cost": s.cp_cost,
                    "unit": root,
                    "target_unit": root,
                    "last_target_unit": target_unit,
                }
                self._queue_reaction(payload)
        except Exception:
            raise
    def _on_fight_attacks_resolved_armour_of_contempt_cleanup(self, unit=None, **_kwargs) -> None:
        if unit is None:
            return
        self._clear_armour_of_contempt_for_attacker(unit)
        self._clear_defensive_effects_for_attacker(unit)

    def _maybe_queue_overwatch(self, moving_unit, action: str, when: str) -> None:
        # Only offer to the opponent of the moving unit's owner
        try:
            owner_player = moving_unit.get_parent_army().player
            if owner_player is self.player:
                return
        except Exception:
            raise
        # Battle Focus: Flitting Shadows prevents Overwatch against this unit for the rest of the turn.
        try:
            sr = getattr(moving_unit, "special_rules", None)
            if isinstance(sr, dict) and sr.get("battle_focus_flitting_shadows_no_overwatch"):
                owner_name = str(sr.get("battle_focus_flitting_shadows_turn_owner", "") or "")
                active_player = getattr(self.game, "get_current_player", lambda: None)()
                active_name = str(getattr(active_player, "id", "") or "")
                if not owner_name or owner_name == active_name:
                    return
        except Exception:
            raise
        # First Prince of Chaos (Shadow Legion Slaanesh): cannot be overwatched.
        try:
            if hasattr(moving_unit, "has_first_prince_slaanesh_no_overwatch") and moving_unit.has_first_prince_slaanesh_no_overwatch():
                return
        except Exception:
            raise
        s = self.get_by_name('FIRE OVERWATCH') or self.get_by_name('Overwatch')
        if not s:
            return
        # Enforce once per turn limit
        if self._used_this_turn.get('OVERWATCH', False):
            return
        # Phase check: Movement or Charge phase per data
        phase_name = self._current_phase_name
        if not s.is_phase_allowed(phase_name or ''):
            return
        # Turn check: opponent's turn
        active_player = getattr(self.game, 'get_current_player', lambda: None)()
        is_active_turn = active_player is self.player
        if not s.is_turn_allowed(is_active_turn):
            # For Overwatch, it should be opponent's turn
            pass
        # CP check
        if self.player.command_points < s.cp_cost:
            return
        # QUICK ELIGIBILITY PRECHECKS per Stratagem text:
        # - Your unit must be within 24" of the enemy unit
        # - Cannot target a TITANIC friendly unit to fire Overwatch
        # - Enemy must be visible to your unit (checked later at use-time; here we only queue if 24" condition holds)
        try:
            candidates = []
            for unit in getattr(self.player.get_army(), 'units', []) or []:
                if not unit.is_alive() or not unit.deployed:
                    continue
                if getattr(unit, 'is_titanic', False):
                    continue  # Restriction: cannot select a TITANIC friendly unit
                # Core rule: Overwatch targets the shooter; battle-shocked units cannot be targeted.
                if _unit_cannot_be_target_of_stratagem(unit):
                    continue
                if hasattr(moving_unit, "is_overwatch_prevented_against"):
                    if moving_unit.is_overwatch_prevented_against(unit, game=self.game):
                        continue
                # Distance check to moving enemy unit (edge-to-edge shortest model pair)
                dist = None
                try:
                    if hasattr(self.game, 'map') and hasattr(self.game.map, 'get_distance_between_units'):
                        dist = self.game.map.get_distance_between_units(unit, moving_unit)
                except Exception:
                    raise
                if dist is not None and dist <= 24.0:
                    candidates.append(unit)
            if not candidates:
                return
        except Exception:
            raise
        # Queue opportunity with minimal context; UI will choose shooter before resolving
        # Deduplicate if same enemy move reaction is already queued
        already = False
        for r in self._pending_reactions:
            if r.get('event') == 'enemy_move' and r.get('stratagem') == s.name and r.get('enemy_unit') is moving_unit:
                already = True
                break
        if not already:
            self._queue_reaction({
                'event': 'enemy_move',
                'when': when,
                'action': action,
                'stratagem': s.name,
                'enemy_unit': moving_unit,
                'phase_name': phase_name,
                'cp_cost': s.cp_cost,
                'candidates': candidates,
            })

    def _maybe_queue_apoplectic_frenzy(self, unit, action: str) -> None:
        try:
            if str(action or "").strip().lower() != "advance":
                return
            if unit is None or not getattr(unit, "is_alive", lambda: True)():
                return
            owner = unit.get_parent_army().player
            if owner is not self.player:
                return
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_berzerker_warband", lambda: False)():
                return
            # Timing: your Movement phase
            if (self._current_phase_name or "").strip().lower() != "movement phase":
                return
            active_player = getattr(self.game, "get_current_player", lambda: None)()
            if active_player is not self.player:
                return
            s = self.get_by_name("APOPLECTIC FRENZY")
            if not s:
                return
            if self.player.command_points < s.cp_cost:
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            if _unit_cannot_be_target_of_stratagem(unit):
                return
            try:
                if not (unit.has_keyword("KHORNE") and unit.has_keyword("BERZERKERS")):
                    return
            except Exception:
                raise
        except Exception:
            raise
        for r in self._pending_reactions:
            if r.get("event") == "unit_advanced" and r.get("stratagem") == s.name and r.get("unit") is unit:
                return
        self._queue_reaction({
            "event": "unit_advanced",
            "phase_name": "Movement phase",
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "unit": unit,
            "target_unit": unit,
            "action": "advance",
        })

    def _maybe_queue_red_wrath(self, unit, action: str) -> None:
        try:
            if str(action or "").strip().lower() != "advance":
                return
            if unit is None or not getattr(unit, "is_alive", lambda: True)():
                return
            owner = unit.get_parent_army().player
            if owner is not self.player:
                return
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if sm_mgr is None or not getattr(sm_mgr, "is_rage_cursed_onslaught", lambda: False)():
                return
            # Timing: your Movement phase
            if (self._current_phase_name or "").strip().lower() != "movement phase":
                return
            active_player = getattr(self.game, "get_current_player", lambda: None)()
            if active_player is not self.player:
                return
            s = self.get_by_name("RED WRATH")
            if not s:
                return
            if self.player.command_points < s.cp_cost:
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            if _unit_cannot_be_target_of_stratagem(unit):
                return
            try:
                if not unit.has_any_keyword("BLOOD ANGELS"):
                    return
            except Exception:
                raise
        except Exception:
            raise
        for r in self._pending_reactions:
            if r.get("event") == "unit_advanced" and r.get("stratagem") == s.name and r.get("unit") is unit:
                return
        self._queue_reaction({
            "event": "unit_advanced",
            "phase_name": "Movement phase",
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "unit": unit,
            "target_unit": unit,
            "action": "advance",
        })

    def _maybe_queue_feigned_retreat(self, unit, action: str) -> None:
        try:
            if str(action or "").strip().lower() != "fall_back":
                return
            if unit is None or not getattr(unit, "is_alive", lambda: True)():
                return
            owner = unit.get_parent_army().player
            if owner is not self.player:
                return
            if not self._is_warhost_detachment():
                return
            if (self._current_phase_name or "").strip().lower() != "movement phase":
                return
            active_player = getattr(self.game, "get_current_player", lambda: None)()
            if active_player is not self.player:
                return
            s = self.get_by_name("FEIGNED RETREAT")
            if not s:
                return
            if self.player.command_points < s.cp_cost:
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            if _unit_cannot_be_target_of_stratagem(unit):
                return
            try:
                if not unit.has_any_keyword("ASURYANI"):
                    return
            except Exception:
                raise
            try:
                if not bool(getattr(getattr(unit, "round_state", None), "fell_back_this_round", False)):
                    return
            except Exception:
                raise
        except Exception:
            raise
        for r in self._pending_reactions:
            if r.get("event") == "unit_move_ended" and r.get("stratagem") == s.name and r.get("unit") is unit:
                return
        self._queue_reaction({
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "unit": unit,
            "target_unit": unit,
            "action": "fall_back",
        })

    def _maybe_queue_cut_down_the_weak(self, unit, action: str) -> None:
        try:
            if str(action or "").strip().lower() != "fall_back":
                return
            if unit is None or not getattr(unit, "is_alive", lambda: True)():
                return
            owner = unit.get_parent_army().player
            if owner is self.player:
                return
            if (self._current_phase_name or "").strip().lower() != "movement phase":
                return
            active_player = getattr(self.game, "get_current_player", lambda: None)()
            if active_player is self.player:
                return
            s = self.get_by_name("CUT DOWN THE WEAK")
            if not s:
                return
            if self.player.command_points < s.cp_cost:
                return
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            try:
                army = self.player.get_army()
            except Exception:
                raise
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is None or not getattr(mgr, "is_peerless_bladesmen", lambda: False)():
                return
        except Exception:
            raise

        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return

        candidates = []
        seen = set()
        for u in list(getattr(army, "units", []) or []):
            try:
                root = u.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                continue
            uid = get_entity_id(root)
            if uid in seen:
                continue
            seen.add(uid)
            try:
                if not root.is_alive():
                    continue
            except Exception:
                continue
            try:
                if not getattr(root, "deployed", False):
                    continue
            except Exception:
                continue
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    continue
            except Exception:
                continue
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    continue
            except Exception:
                raise
            try:
                if not mgr.is_emperors_children_unit(root):
                    continue
            except Exception:
                raise
            try:
                if root.has_keyword("Vehicle") and not root.has_keyword("Walker"):
                    continue
            except Exception:
                raise
            try:
                dist = float(game_map.get_distance_between_units(root, unit))
            except Exception:
                continue
            if dist > 6.0:
                continue
            try:
                if not root.can_declare_charge_against(unit, self.game, out_of_turn=True):
                    continue
            except Exception:
                raise
            candidates.append(root)

        if not candidates:
            return
        for r in self._pending_reactions:
            if r.get("event") == "unit_move_ended" and r.get("stratagem") == s.name and r.get("enemy_unit") is unit:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "enemy_unit": unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    # Command Re-roll trigger on roll_made for active player only
    def _on_roll_made(self, player, unit, roll_type: str, value, reroll, dice=None, **kwargs):
        # If some other rule already rerolled/locks this roll (10e: a dice can't be re-rolled more than once),
        # do not offer Command Re-roll.
        try:
            if bool(kwargs.get("reroll_locked", False)):
                return
        except Exception:
            raise
        try:
            from ..utility.reroll_tracker import get_reroll_tracker
            tracker = get_reroll_tracker(self.game)
            roll_id = kwargs.get("roll_id", None)
            if tracker is not None and roll_id is not None and tracker.is_used(roll_id):
                return
        except Exception:
            raise
        if player is not self.player:
            return
        s = self.get_by_name('COMMAND RE-ROLL')
        if not s:
            return
        # Core rules: cannot use the same stratagem more than once per phase (per player).
        try:
            if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
        except Exception:
            raise
        phase_name = self._current_phase_name
        if not s.is_phase_allowed(phase_name or ''):
            return
        if not s.is_turn_allowed(True):
            return
        if self.player.command_points < s.cp_cost:
            return
        # Queue re-roll opportunity with a callable to execute reroll if chosen
        self._queue_reaction({
            'event': 'roll_made',
            'stratagem': s.name,
            'unit': unit,
            'roll_type': roll_type,
            'value': value,
            'dice': dice,
            'phase_name': phase_name,
            'cp_cost': s.cp_cost,
            'reroll': reroll,
        })

    def _on_model_destroyed(
        self,
        attacker_model=None,
        attacker_unit=None,
        target_model=None,
        target_unit=None,
        weapon_profile=None,
        **kwargs,
    ) -> None:
        """
        Faction stratagem reactions that trigger "just after" a model is destroyed.
        """
        # WORLD EATERS: SKULLS FOR THE SKULL THRONE!
        try:
            s = self.get_by_name("SKULLS FOR THE SKULL THRONE!")
        except Exception:
            raise
        def _handle_skulls_for_the_skull_throne():
            if not s:
                return
            # Must be your stratagem manager's player army, in Fight phase (per stratagem text).
            if attacker_unit is None or target_unit is None:
                return
            try:
                if attacker_unit.get_parent_army().player is not self.player:
                    return
            except Exception:
                raise
            try:
                if attacker_unit.get_parent_army() == target_unit.get_parent_army():
                    return
            except Exception:
                raise
            try:
                unit = attacker_unit.get_attached_unit_root()
            except Exception:
                raise
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_berzerker_warband", lambda: False)():
                return
            try:
                if _unit_cannot_be_target_of_stratagem(unit):
                    return
            except Exception:
                raise
            try:
                if not (hasattr(unit, "has_any_keyword") and unit.has_any_keyword("WORLD EATERS")):
                    return
            except Exception:
                raise
            # Ensure current phase is Fight phase
            phase_name = self._current_phase_name
            if not (phase_name and phase_name.strip().lower() == "fight phase"):
                return
            # Must be a melee kill (Fight phase should imply, but be explicit).
            try:
                parent = getattr(weapon_profile, "parent_wargear", None)
                if parent is None or not parent.is_melee():
                    return
            except Exception:
                raise
            # Target must be CHARACTER or MONSTER model (approximate via unit keywords)
            try:
                is_char = bool(target_unit.has_keyword("Character"))
                is_mon = bool(target_unit.has_keyword("Monster"))
                if not (is_char or is_mon):
                    return
            except Exception:
                raise
            # Check CP / turn / phase gating
            if not s.can_use(self.player, self.game, phase_name=phase_name):
                return
            # Deduplicate same reaction for same attacker+target model in this phase
            for r in self._pending_reactions:
                try:
                    if r.get("event") == "model_destroyed" and r.get("stratagem") == s.name and r.get("attacker_unit") is unit and r.get("target_model") is target_model:
                        return
                except Exception:
                    raise
            self._queue_reaction({
                "event": "model_destroyed",
                "phase_name": phase_name,
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "attacker_unit": unit,
                "unit": unit,
                "target_model": target_model,
                "target_unit": target_unit,
            })

        _handle_skulls_for_the_skull_throne()

        # WORLD EATERS: A WORTHY SKULL (track eligible kills for later prompt).
        try:
            if attacker_unit is None or target_unit is None:
                return
            if (self._current_phase_name or "").strip().lower() != "fight phase":
                return
            try:
                if attacker_unit.get_parent_army().player is not self.player:
                    return
            except Exception:
                raise
            try:
                if attacker_unit.get_parent_army() == target_unit.get_parent_army():
                    return
            except Exception:
                raise
            try:
                parent = getattr(weapon_profile, "parent_wargear", None)
                if parent is not None and not parent.is_melee():
                    return
            except Exception:
                raise
            is_char = False
            is_mon = False
            try:
                is_char = bool(getattr(target_model, "is_character", False))
            except Exception:
                raise
            try:
                is_mon = bool(target_unit.has_keyword("Monster"))
            except Exception:
                raise
            if not (is_char or is_mon):
                return
            try:
                root = attacker_unit.get_attached_unit_root()
            except Exception:
                raise
            self._worthy_skull_kills[root] = True
        except Exception:
            raise
    def _on_model_destroyed_before_removal(self, unit=None, model=None, **_kwargs) -> None:
        """
        Faction stratagem reactions that trigger before the destroyed model is removed.
        """
        # WORLD EATERS (Khorne Daemonkin): SUMMONED BY SLAUGHTER
        try:
            s = self.get_by_name("SUMMONED BY SLAUGHTER")
        except Exception:
            raise
        if s is None or unit is None or model is None:
            return

        try:
            root = unit.get_attached_unit_root()
        except Exception:
            raise
        # Trigger only when the last model in the attached unit is destroyed.
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            raise
        alive_others = [m for m in models if getattr(m, "is_alive", True) and m is not model]
        if alive_others:
            return

        try:
            army = root.get_parent_army()
        except Exception:
            raise
        we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
            return

        try:
            br = int(getattr(self.game, "turn", 0) or 0)
        except Exception:
            raise
        if br and int(self._used_battle_round.get("SUMMONED BY SLAUGHTER", 0) or 0) == br:
            return

        candidates = []
        seen = set()
        try:
            units = list(getattr(army, "units", []) or [])
        except Exception:
            raise
        for u in units:
            try:
                cand = u.get_attached_unit_root()
            except Exception:
                raise
            if cand is None:
                continue
            try:
                uid = get_entity_id(cand)
            except Exception:
                raise
            if uid in seen:
                continue
            seen.add(uid)
            try:
                if not cand.is_in_reserves():
                    continue
            except Exception:
                raise
            try:
                if not cand.is_alive():
                    continue
            except Exception:
                raise
            if not self._is_bloodletters_unit(cand):
                continue
            try:
                if _unit_cannot_be_target_of_stratagem(cand):
                    continue
            except Exception:
                raise
            candidates.append(cand)

        if not candidates:
            return

        phase_name = self._current_phase_name or ""
        if not s.can_use(self.player, self.game, phase_name=phase_name):
            return

        try:
            destroyed_base = copy.deepcopy(getattr(model, "model_base", None))
        except Exception:
            raise
        self._queue_reaction({
            "event": "model_destroyed_before_removal",
            "phase_name": phase_name,
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "destroyed_unit": root,
            "destroyed_model": model,
            "destroyed_model_base": destroyed_base,
            "candidates": candidates,
        })

    def _on_unit_destroyed(self, unit=None, last_model=None, **kwargs) -> None:
        """
        Faction stratagem reactions that trigger when a unit is destroyed.
        """
        # EMPEROR'S CHILDREN: track units that destroyed enemies in their Fight phase.
        try:
            destroyed_by_unit = kwargs.get("destroyed_by_unit")
            if destroyed_by_unit is not None and self.game is not None:
                phase_name = str(self._current_phase_name or "").strip().lower()
                active_player = getattr(self.game, "get_current_player", lambda: None)()
                if phase_name == "fight phase" and active_player is self.player:
                    try:
                        if destroyed_by_unit.get_parent_army().player is self.player:
                            army = destroyed_by_unit.get_parent_army()
                        else:
                            army = None
                    except Exception:
                        army = None
                    mgr = getattr(army, "emperors_children", None) if army is not None else None
                    if mgr is not None and getattr(mgr, "is_peerless_bladesmen", lambda: False)():
                        try:
                            if mgr.is_emperors_children_unit(destroyed_by_unit):
                                root = destroyed_by_unit.get_attached_unit_root()
                                if root is not None:
                                    self._ec_units_destroyed_enemy_in_fight.add(get_entity_id(root))
                        except Exception:
                            raise
        except Exception:
            raise
        # Rage-cursed Onslaught: A GRIM WARNING
        try:
            s = self.get_by_name("A GRIM WARNING")
        except Exception:
            raise
        if s:
            if unit is None or self.game is None:
                return
            try:
                if unit.get_parent_army().player is not self.player:
                    return
            except Exception:
                raise
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if sm_mgr is None or not getattr(sm_mgr, "is_rage_cursed_onslaught", lambda: False)():
                return
            try:
                if not unit.has_any_keyword("BLOOD ANGELS"):
                    return
            except Exception:
                raise
            # Must have objective control snapshot from end of previous phase.
            snapshot = getattr(self.game, "_objective_control_snapshot", None)
            if not isinstance(snapshot, dict) or not snapshot:
                return
            # Determine unit position from last model (unit may already be empty).
            pos = None
            if last_model is not None:
                try:
                    pos = last_model.get_location()
                except Exception:
                    raise
            if pos is None:
                try:
                    pos = getattr(unit, "position", None)
                except Exception:
                    pos = None
            if pos is None:
                return
            try:
                ux, uy = float(pos[0]), float(pos[1])
            except Exception:
                raise
            candidates = []
            for obj in list(getattr(self.game.map, "objectives", []) or []):
                try:
                    loc = getattr(obj, "location", None)
                    if loc is None or getattr(loc, "removed", False):
                        continue
                    if snapshot.get(loc) is not self.player:
                        continue
                    radius = float(getattr(loc, "control_radius", 0.0) or 0.0)
                    base_radius = 0.0
                    try:
                        base = getattr(last_model, "model_base", None)
                        if base is not None:
                            base_radius = float(getattr(base, "base_size", 0.0) or 0.0)
                    except Exception:
                        raise
                    dx = ux - float(getattr(loc, "x", 0.0))
                    dy = uy - float(getattr(loc, "y", 0.0))
                    if (dx * dx + dy * dy) ** 0.5 <= (radius + base_radius):
                        candidates.append(obj)
                except Exception:
                    raise
            if not candidates:
                return
            if self.player.command_points < s.cp_cost:
                return
            try:
                if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                    return
            except Exception:
                raise
            # Deduplicate per unit destruction
            for r in self._pending_reactions:
                if r.get("event") == "unit_destroyed" and r.get("stratagem") == s.name and r.get("unit") is unit:
                    return
            self._queue_reaction({
                "event": "unit_destroyed",
                "phase_name": self._current_phase_name,
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "unit": unit,
                "objective_candidates": candidates,
            })

        # WORLD EATERS: BLOOD OFFERING
        try:
            s = self.get_by_name("BLOOD OFFERING")
        except Exception:
            raise
        if s:
            if unit is None or self.game is None:
                return
            try:
                if unit.get_parent_army().player is not self.player:
                    return
            except Exception:
                raise
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_berzerker_warband", lambda: False)():
                return
            try:
                if not unit.has_any_keyword("WORLD EATERS"):
                    return
            except Exception:
                raise
            # Must have objective control snapshot from end of previous phase.
            snapshot = getattr(self.game, "_objective_control_snapshot", None)
            if not isinstance(snapshot, dict) or not snapshot:
                return
            # Determine unit position from last model (unit may already be empty).
            pos = None
            if last_model is not None:
                try:
                    pos = last_model.get_location()
                except Exception:
                    raise
            if pos is None:
                return
            try:
                ux, uy = float(pos[0]), float(pos[1])
            except Exception:
                raise
            candidates = []
            for obj in list(getattr(self.game.map, "objectives", []) or []):
                try:
                    loc = getattr(obj, "location", None)
                    if loc is None or getattr(loc, "removed", False):
                        continue
                    if snapshot.get(loc) is not self.player:
                        continue
                    radius = float(getattr(loc, "control_radius", 0.0) or 0.0)
                    base_radius = 0.0
                    try:
                        base = getattr(last_model, "model_base", None)
                        if base is not None:
                            base_radius = float(getattr(base, "base_size", 0.0) or 0.0)
                    except Exception:
                        raise
                    dx = ux - float(getattr(loc, "x", 0.0))
                    dy = uy - float(getattr(loc, "y", 0.0))
                    if (dx * dx + dy * dy) ** 0.5 <= (radius + base_radius):
                        candidates.append(obj)
                except Exception:
                    raise
            if not candidates:
                return
            if self.player.command_points < s.cp_cost:
                return
            try:
                if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
                    return
            except Exception:
                raise
            # Deduplicate per unit destruction
            for r in self._pending_reactions:
                if r.get("event") == "unit_destroyed" and r.get("stratagem") == s.name and r.get("unit") is unit:
                    return
            self._queue_reaction({
                "event": "unit_destroyed",
                "phase_name": self._current_phase_name,
                "stratagem": s.name,
                "cp_cost": s.cp_cost,
                "unit": unit,
                "objective_candidates": candidates,
            })

        # EMPEROR'S CHILDREN: UNBOUND ARROGANCE
        try:
            s = self.get_by_name("UNBOUND ARROGANCE")
        except Exception:
            raise
        if not s:
            return
        destroyed_by_unit = kwargs.get("destroyed_by_unit")
        if destroyed_by_unit is None or self.game is None:
            return
        try:
            if destroyed_by_unit.get_parent_army().player is not self.player:
                return
        except Exception:
            raise
        try:
            if unit is not None and unit.get_parent_army().player is self.player:
                return
        except Exception:
            raise
        try:
            army = destroyed_by_unit.get_parent_army()
        except Exception:
            raise
        mgr = getattr(army, "emperors_children", None) if army is not None else None
        if mgr is None or not getattr(mgr, "is_coterie_of_conceited", lambda: False)():
            return
        try:
            if not mgr.is_emperors_children_unit(destroyed_by_unit):
                return
        except Exception:
            raise
        phase_name = str(self._current_phase_name or "").strip().lower()
        if phase_name not in ("shooting phase", "fight phase"):
            return
        br = int(getattr(self.game, "turn", 0) or 0)
        try:
            if br > 0 and int(getattr(mgr, "unbound_arrogance_used_round", 0) or 0) == br:
                return
        except Exception:
            raise
        if not s.can_use(self.player, self.game, unit=destroyed_by_unit, phase_name=self._current_phase_name):
            return
        for r in self._pending_reactions:
            try:
                if r.get("event") == "unit_destroyed" and r.get("stratagem") == s.name and r.get("unit") is destroyed_by_unit and r.get("enemy_unit") is unit:
                    return
            except Exception:
                raise
        self._queue_reaction({
            "event": "unit_destroyed",
            "phase_name": self._current_phase_name,
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "unit": destroyed_by_unit,
            "target_unit": destroyed_by_unit,
            "enemy_unit": unit,
        })

    # -------- Public API --------
    def list_available(self) -> List[Stratagem]:
        return list(self.available)

    def get_by_name(self, name: str) -> Optional[Stratagem]:
        for s in self.available:
            if s.name.lower() == name.lower():
                return s
        return None

    def can_use(self, name: str, **kwargs) -> bool:
        s = self.get_by_name(name)
        if not s:
            return False
        return s.can_use(self.player, self.game, **kwargs)

    def use(self, name: str, **kwargs) -> bool:
        s = self.get_by_name(name)
        if not s:
            return False

        name_u = (s.name or "").strip().upper()
        if name_u == "GILDED CHAMPION":
            model = self._resolve_gilded_champion_model(kwargs)
            if model is not None:
                kwargs["model"] = model
                root = self._gilded_champion_target_root(model)
                if root is not None:
                    kwargs.setdefault("target_unit", root)
                    kwargs.setdefault("unit", root)
            if "phase_name" not in kwargs:
                kwargs["phase_name"] = self._gilded_champion_resolve_phase_name("", self.game)

        # Core restriction: a player cannot use the same Stratagem more than once in the same phase.
        # Applies to all stratagems (including ones usable in "Any phase"), unless an ability explicitly
        # names the stratagem (not implemented as a generic bypass).
        try:
            phase_name = kwargs.get("phase_name") or self._current_phase_name
            if phase_name:
                key = (s.name or "").strip().upper()
                if key and key in self._used_stratagems_this_phase:
                    if key == "HEROIC INTERVENTION" and self._heroic_intervention_repeat_allowed(
                        target_unit=kwargs.get("target_unit") or kwargs.get("unit"),
                        candidates=kwargs.get("candidates"),
                    ):
                        pass
                    else:
                        print(f"ERROR: Cannot use {s.name} more than once in the same phase (core rules)")
                        return False
        except Exception:
            raise
        # Targeting restrictions (manager layer too, since several special-cases bypass Stratagem.use()).
        # - Embarked units cannot be targeted by stratagems (no exceptions here).
        # - Battle-shocked units cannot be targeted by stratagems, except INSANE BRAVERY.
        try:
            tgt = _extract_friendly_target_unit_from_kwargs(kwargs)
            name_u = (s.name or "").strip().upper()
            if name_u not in ("BLOOD OFFERING", "A GRIM WARNING") and _unit_cannot_be_target_of_stratagem(tgt):
                if name_u == "INSANE BRAVERY":
                    # Only bypass battle-shock restriction, not embarked restriction.
                    try:
                        if bool(getattr(tgt, "is_embarked", False)):
                            print("ERROR: Cannot target an embarked unit with a Stratagem")
                            return False
                    except Exception:
                        raise
                    try:
                        if getattr(tgt, "embarked_in", None) is not None:
                            print("ERROR: Cannot target an embarked unit with a Stratagem")
                            return False
                    except Exception:
                        raise
                    # If the unit is battle-shocked, allow INSANE BRAVERY.
                    try:
                        is_bs = getattr(tgt, "is_battle_shocked", None)
                        if callable(is_bs) and bool(is_bs()):
                            pass
                        else:
                            return False
                    except Exception:
                        raise
                else:
                    print("ERROR: Cannot target a Battle-shocked or embarked unit with a Stratagem")
                    return False
        except Exception:
            raise
        # Adeptus Custodes (Lions of the Emperor): GILDED CHAMPION
        if name_u == "GILDED CHAMPION":
            model = kwargs.get("model") or self._resolve_gilded_champion_model(kwargs)
            prepared = self._gilded_champion_prepare(
                model=model,
                ability_key=str(kwargs.get("ability_key", "") or ""),
                ability_name=str(kwargs.get("ability_name", "") or ""),
                phase_name=str(kwargs.get("phase_name", "") or ""),
                source=str(kwargs.get("source", "datasheet") or "datasheet"),
                game=self.game,
            )
            if prepared is None:
                print("ERROR: GILDED CHAMPION: invalid target or context")
                return False
            target_unit = prepared.get("target_unit")
            eff_cost = s.cp_cost
            apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
            if callable(apply_fn):
                preview = apply_fn(s, target_unit=target_unit) or {}
                eff_cost = int(preview.get("cost", s.cp_cost))
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            model_obj = prepared.get("model")
            if model_obj is None or not hasattr(model_obj, "grant_once_per_battle_extra_use"):
                return False
            model_obj.grant_once_per_battle_extra_use(prepared.get("ability_key", ""), uses=1)
            self._gilded_champion_used_models.add(str(prepared.get("model_id", "") or ""))
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            self._used_stratagems_this_phase.add(name_u)
            ability_label = str(prepared.get("ability_name", "") or prepared.get("ability_key", "") or "ability")
            model_name = str(getattr(model_obj, "name", "Model") or "Model")
            print(f"INFO: GILDED CHAMPION: {model_name} can use {ability_label} one additional time (not this phase).")
            return True
        # Adeptus Custodes (Lions of the Emperor): UNLEASH THE LIONS
        if name_u == "UNLEASH THE LIONS":
            target_unit = kwargs.get("target_unit") or kwargs.get("unit")
            if target_unit is None:
                print("ERROR: UNLEASH THE LIONS: no target unit provided")
                return False
            if self._unleash_lions_detachment_manager() is None:
                print("ERROR: UNLEASH THE LIONS: wrong detachment")
                return False
            if not self._unleash_lions_is_valid_target(target_unit):
                print("ERROR: UNLEASH THE LIONS: invalid target (must be Allarus/Aquilon on battlefield)")
                return False
            if "phase_name" not in kwargs:
                kwargs["phase_name"] = self._current_phase_name
            if not s.can_use(self.player, self.game, **kwargs):
                print("ERROR: UNLEASH THE LIONS: cannot be used in current state")
                return False
            eff_cost = s.cp_cost
            apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
            if callable(apply_fn):
                preview = apply_fn(s, target_unit=target_unit) or {}
                eff_cost = int(preview.get("cost", s.cp_cost))
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            from ..utility.unit_split import split_unit_into_single_model_units

            root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
            resulting = split_unit_into_single_model_units(root, game=self.game)
            if not resulting:
                print("WARN: UNLEASH THE LIONS: no units created during split")
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            self._used_stratagems_this_phase.add(name_u)
            try:
                count = len(resulting) if resulting is not None else 0
                root_name = getattr(root, "name", "Unit") if root is not None else "Unit"
                print(f"INFO: UNLEASH THE LIONS: {root_name} split into {max(1, count)} unit(s).")
            except Exception:
                pass
            return True
        # Core: INSANE BRAVERY (auto-pass a Battle-shock test about to be taken; once per battle)
        if s.name.upper() == "INSANE BRAVERY":
            if self._used_once_per_battle.get("INSANE BRAVERY", False):
                print("WARN: INSANE BRAVERY can only be used once per battle")
                return False
            target = kwargs.get("unit")
            if not target:
                print("ERROR: INSANE BRAVERY: no target unit provided")
                return False
            # Spend CP
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=unit).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            # Mark auto-pass flag to be consumed by Unit.take_battle_shock_test()
            try:
                sr = getattr(target, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["auto_pass_next_battle_shock_test"] = True
                target.special_rules = sr
            except Exception:
                raise
            self._used_once_per_battle["INSANE BRAVERY"] = True
            try:
                print(f"INFO: INSANE BRAVERY used on {getattr(target, 'name', 'Unit')}: next Battle-shock test auto-passes (once per battle)")
            except Exception:
                raise
            if kwargs.get('dequeue') is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            return True

        # Core: COUNTER-OFFENSIVE
        if s.name.upper() == "COUNTER-OFFENSIVE":
            target_unit = kwargs.get("target_unit") or kwargs.get("unit")
            if target_unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "COUNTER-OFFENSIVE":
                        cands = r.get("candidates") or []
                        if cands:
                            target_unit = cands[0]
                        break
            if target_unit is None:
                print("ERROR: COUNTER-OFFENSIVE: no target unit provided")
                return False
            if (self._current_phase_name or "").strip().lower() != "fight phase":
                print("ERROR: COUNTER-OFFENSIVE: not in Fight phase")
                return False
            fight_mgr = getattr(self.game, "fight_phase_manager", None)
            try:
                if fight_mgr and hasattr(fight_mgr, "_canonical_unit_for_fight"):
                    target_unit = fight_mgr._canonical_unit_for_fight(target_unit)
            except Exception:
                raise
            try:
                if target_unit.get_parent_army().player is not self.player:
                    print("ERROR: COUNTER-OFFENSIVE: target unit is not yours")
                    return False
            except Exception:
                raise
            try:
                if fight_mgr and hasattr(fight_mgr, "fought_units") and target_unit in fight_mgr.fought_units:
                    print("ERROR: COUNTER-OFFENSIVE: target unit already fought this phase")
                    return False
            except Exception:
                raise
            try:
                if getattr(target_unit, "round_state", None) and getattr(target_unit.round_state, "fought_this_phase", False):
                    print("ERROR: COUNTER-OFFENSIVE: target unit already fought this phase")
                    return False
            except Exception:
                raise
            try:
                if hasattr(target_unit, "is_eligible_to_fight") and callable(target_unit.is_eligible_to_fight):
                    if not target_unit.is_eligible_to_fight(self.game.map):
                        print("ERROR: COUNTER-OFFENSIVE: target unit is not eligible to fight")
                        return False
            except Exception:
                raise
            if not fight_mgr or not hasattr(fight_mgr, "force_next_unit"):
                print("ERROR: WARNING: COUNTER-OFFENSIVE: fight phase manager not available")
                return False
            try:
                if not fight_mgr.force_next_unit(target_unit, self.player):
                    print("ERROR: COUNTER-OFFENSIVE: could not force unit to fight next")
                    return False
            except Exception:
                raise
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                try:
                    fight_mgr._forced_next_unit = None
                    fight_mgr._forced_next_player = None
                except Exception:
                    raise
                return False
            try:
                if getattr(fight_mgr, "_current_player", None) is not None and getattr(fight_mgr, "_opponent_player", None) is not None:
                    fight_mgr._request_unit_selection(fight_mgr._current_player, fight_mgr._opponent_player)
            except Exception:
                raise
            if kwargs.get('dequeue') is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            return True

        # Core: SMOKESCREEN (Benefit of Cover + Stealth until end of phase)
        if s.name.upper() == "SMOKESCREEN":
            target_unit = kwargs.get("target_unit") or kwargs.get("unit")
            if not target_unit:
                # Try candidates from pending
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "SMOKESCREEN":
                        cands = r.get("candidates") or []
                        if cands:
                            target_unit = cands[0]
                        break
            if not target_unit:
                print("ERROR: SMOKESCREEN: missing target unit")
                return False
            # Target must be SMOKE
            try:
                if not (hasattr(target_unit, "has_keyword") and target_unit.has_keyword("SMOKE")):
                    print("ERROR: SMOKESCREEN: target is not a SMOKE unit")
                    return False
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=unit).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(target_unit, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["smokescreen_active"] = True
                target_unit.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: SMOKESCREEN: {getattr(target_unit, 'name', 'Unit')} gains Benefit of Cover + Stealth until end of phase.")
            return True

        # Armour of Contempt / The Foe Foreseen: worsen AP by 1 vs a selected ADEPTUS ASTARTES unit.
        if s.name.upper() in ("ARMOUR OF CONTEMPT", "THE FOE FORESEEN"):
            target_unit = kwargs.get("target_unit") or kwargs.get("unit")
            attacker_unit = kwargs.get("attacker_unit")
            if target_unit is None or attacker_unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == s.name.upper():
                        cands = r.get("candidates") or []
                        if target_unit is None and cands:
                            target_unit = cands[0]
                        attacker_unit = attacker_unit or r.get("attacking_unit")
                        break
            if target_unit is None or attacker_unit is None:
                print(f"ERROR: {s.name}: missing target context")
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() not in ("shooting phase", "fight phase"):
                print(f"ERROR: {s.name}: wrong phase")
                return False
            try:
                if attacker_unit.get_parent_army().player is self.player:
                    print(f"INFO: {s.name}: must be used in opponent's phase")
                    return False
            except Exception:
                raise
            try:
                if target_unit.get_parent_army().player is not self.player:
                    print(f"ERROR: {s.name}: target unit is not yours")
                    return False
            except Exception:
                raise
            try:
                if not target_unit.has_any_keyword("ADEPTUS ASTARTES"):
                    print(f"ERROR: {s.name}: target is not ADEPTUS ASTARTES")
                    return False
            except Exception:
                raise
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            if not self._apply_armour_of_contempt(target_unit, attacker_unit, amount=1):
                return False
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: {s.name}: {getattr(target_unit, 'name', 'Unit')} worsens AP by 1 vs {getattr(attacker_unit, 'name', 'attacker')}.")
            return True
        # Special-case: FIRE OVERWATCH full resolution
        if s.name.upper() in ("FIRE OVERWATCH", "OVERWATCH"):
            enemy_unit = kwargs.get("enemy_unit")
            if not enemy_unit:
                # Try to take from last pending
                if self._pending_reactions:
                    for r in self._pending_reactions:
                        if r.get('stratagem','').upper() in ("FIRE OVERWATCH", "OVERWATCH"):
                            enemy_unit = r.get('enemy_unit')
                            break
            if not enemy_unit:
                print("ERROR: Overwatch: no enemy unit context")
                return False
            # Choose shooter unit
            shooter = kwargs.get("shooter_unit")
            if not shooter:
                # Prefer candidates if present, else find any within 24"
                candidates = []
                try:
                    for unit in getattr(self.player.get_army(), 'units', []) or []:
                        if not unit.is_alive() or not unit.deployed:
                            continue
                        if getattr(unit, 'is_titanic', False):
                            continue
                        # Core rule: Overwatch targets the shooter; battle-shocked units cannot be targeted.
                        if _unit_cannot_be_target_of_stratagem(unit):
                            continue
                        dist = None
                        try:
                            if hasattr(self.game, 'map') and hasattr(self.game.map, 'get_distance_between_units'):
                                dist = self.game.map.get_distance_between_units(unit, enemy_unit)
                        except Exception:
                            raise
                        if dist is not None and dist <= 24.0:
                            candidates.append(unit)
                except Exception:
                    raise
                # Pick heuristic: most ranged weapons
                if candidates:
                    shooter = max(candidates, key=lambda u: sum(1 for m in u.models for w in getattr(m, 'wargear', []) if getattr(w, 'is_ranged', lambda: False)()))
            if not shooter:
                print("ERROR: Overwatch: no eligible shooter in 24\"")
                return False
            # Even if a shooter was explicitly provided, enforce battle-shock restriction.
            if _unit_cannot_be_target_of_stratagem(shooter):
                print("ERROR: Overwatch: cannot target a Battle-shocked unit")
                return False
            # Build declarations: group best ranged profile per model for target
            declarations = []
            profile_to_models = {}
            for model in shooter.models:
                if not getattr(model, 'is_alive', False):
                    continue
                best_profile = None
                best_score = -1.0
                for wargear in getattr(model, 'wargear', []) or []:
                    if not getattr(wargear, 'is_ranged', lambda: False)():
                        continue
                    for _, profile in getattr(wargear, 'profiles', {}).items():
                        try:
                            score = float(profile.get_damage_potential(enemy_unit))
                        except Exception:
                            raise
                        if score > best_score:
                            best_score = score
                            best_profile = profile
                if best_profile is not None:
                    profile_to_models.setdefault(best_profile, []).append(model)
            for profile, models in profile_to_models.items():
                declarations.append({'weapon_profile': profile, 'target_unit': enemy_unit, 'models': models})
            if not declarations:
                print("ERROR: Overwatch: no ranged weapons eligible")
                return False
            # Apply Overwatch hit restriction: only unmodified 6 hits
            ok = False
            out_of_phase = True
            try:
                setattr(shooter, '_overwatch_sixes_only', True)
                print(f"INFO: Overwatch: {shooter.name} firing at {enemy_unit.name} ({len(declarations)} weapons)")
                ok = shooter.execute_shooting_declarations(declarations, self.game.map, out_of_phase=out_of_phase)
            finally:
                try:
                    delattr(shooter, '_overwatch_sixes_only')
                except Exception:
                    raise
                # If execution failed, ensure we do not mark the unit as having shot
                if (not ok) and (not out_of_phase) and getattr(shooter, 'round_state', None):
                    shooter.round_state.shot_this_round = False
            if ok:
                # Mark once per turn consumed
                self._used_this_turn['OVERWATCH'] = True
                # If this was a queued reaction, drop it
                if kwargs.get('dequeue') is True:
                    self._dequeue_reaction_by_name(s.name)
                # Spend CP and return through normal use path (so CP is deducted consistently)
                if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                    print("ERROR: Overwatch succeeded but CP spend failed; adjusting CP manually")
                try:
                    self._used_stratagems_this_phase.add((s.name or "").strip().upper())
                except Exception:
                    raise
                return True
            else:
                print("ERROR: Overwatch: shooting failed or invalid")
                return False

        # Special-case: COMMAND RE-ROLL
        if s.name.upper() == "COMMAND RE-ROLL":
            # Find the pending roll context if not provided
            roll_type = kwargs.get('roll_type')
            reroll_cb = kwargs.get('reroll')
            unit = kwargs.get('unit')
            dice = kwargs.get('dice')
            value = kwargs.get('value')
            if not reroll_cb:
                for r in reversed(self._pending_reactions):
                    if r.get('stratagem', '').upper() == 'COMMAND RE-ROLL':
                        reroll_cb = r.get('reroll')
                        roll_type = roll_type or r.get('roll_type')
                        unit = unit or r.get('unit')
                        dice = dice or r.get('dice')
                        value = value or r.get('value')
                        break
            if not callable(reroll_cb):
                print("ERROR: Command Re-roll: no reroll callback available")
                return False
            # Spend CP first per rules, then perform the reroll
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                result = reroll_cb()
                # Optional: log outcome
                try:
                    name = getattr(unit, 'name', 'Unit') if unit else 'Unit'
                    if roll_type == 'advance':
                        print(f"INFO: Command Re-roll: {name} new advance roll -> {result}")
                    elif roll_type == 'charge':
                        total = result[0] if isinstance(result, (list, tuple)) else result
                        print(f"INFO: Command Re-roll: {name} new charge roll -> {total}")
                    elif roll_type == 'hazardous':
                        print(f"INFO: Command Re-roll: {name} new hazardous roll -> {result}")
                    elif roll_type in ('hit','wound','save','damage','attacks'):
                        print(f"INFO: Command Re-roll: {name} new {roll_type} roll -> {result}")
                    else:
                        print(f"INFO: Command Re-roll executed ({roll_type})")
                except Exception:
                    raise
                # Remove the matching pending reaction if present
                for i in range(len(self._pending_reactions)-1, -1, -1):
                    if self._pending_reactions[i].get('stratagem', '').upper() == 'COMMAND RE-ROLL':
                        self._pending_reactions.pop(i)
                        break
                try:
                    self._used_stratagems_this_phase.add((s.name or "").strip().upper())
                except Exception:
                    raise
                return True
            except Exception as e:
                raise
        # Core: EPIC CHALLENGE (grant Precision to a selected CHARACTER model's melee attacks until end of phase)
        if s.name.upper() == "EPIC CHALLENGE":
            unit = kwargs.get("unit")
            model = kwargs.get("model")
            # Try to resolve from pending reaction context
            if unit is None or model is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "EPIC CHALLENGE":
                        unit = unit or r.get("unit")
                        elig = r.get("eligible_models") or []
                        model = model or (elig[0] if elig else None)
                        break
            if unit is None or model is None:
                print("ERROR: EPIC CHALLENGE: missing unit/model context")
                return False
            # Must be a CHARACTER model in your unit
            try:
                pu = getattr(model, "parent_unit", None)
                if pu is None or pu is not unit:
                    # Some internal structures may wrap, so accept as long as model is in unit.models
                    if model not in list(getattr(unit, "models", []) or []):
                        return False
            except Exception:
                raise
            try:
                if not bool(getattr(model, "is_character", False)):
                    pu = getattr(model, "parent_unit", None)
                    fn = getattr(pu, "has_keyword_local", None)
                    if callable(fn):
                        if not bool(fn("Character")):
                            return False
                    else:
                        if not hasattr(pu, "keywords"):
                            if not bool(getattr(pu, "is_character", False)):
                                return False
                        else:
                            kws = getattr(pu, "keywords", []) or []
                            if "character" not in [str(k).lower() for k in kws]:
                                return False
            except Exception:
                raise
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(model, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["epic_challenge_precision_active"] = True
                model.special_rules = sr
                self._epic_challenge_models.append(model)
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: EPIC CHALLENGE: {getattr(model, 'name', 'Character')} gains [PRECISION] on melee attacks until end of phase.")
            return True

        # EMPEROR'S CHILDREN: UNBOUND ARROGANCE
        if s.name.upper() == "UNBOUND ARROGANCE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "UNBOUND ARROGANCE":
                        unit = r.get("unit") or r.get("target_unit")
                        break
            if unit is None:
                print("ERROR: UNBOUND ARROGANCE: missing target unit context")
                return False
            try:
                army = self.player.get_army()
            except Exception:
                raise
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is None or not getattr(mgr, "is_coterie_of_conceited", lambda: False)():
                return False
            try:
                if not mgr.is_emperors_children_unit(unit):
                    return False
            except Exception:
                raise
            br = int(getattr(self.game, "turn", 0) or 0)
            if br <= 0:
                return False
            try:
                if int(getattr(mgr, "unbound_arrogance_used_round", 0) or 0) == br:
                    return False
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=unit).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                new_val = mgr.increase_pledge(1)
            except Exception:
                raise
            try:
                mgr.unbound_arrogance_used_round = br
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            if new_val is None:
                try:
                    print("INFO: UNBOUND ARROGANCE: pledge increased by 1")
                except Exception:
                    raise
            else:
                try:
                    print(f"INFO: UNBOUND ARROGANCE: pledge increased to {new_val}")
                except Exception:
                    raise
            return True

        # EMPEROR'S CHILDREN: DEATH ECSTASY
        if s.name.upper() == "DEATHLESS DUTY":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            attacker_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
            candidates = list(kwargs.get("candidates") or kwargs.get("target_units") or [])
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "DEATHLESS DUTY":
                        unit = unit or r.get("unit") or r.get("target_unit")
                        attacker_unit = attacker_unit or r.get("attacking_unit")
                        if not candidates:
                            candidates = list(r.get("candidates") or r.get("target_units") or [])
                        break
            if unit is None:
                print("ERROR: DEATHLESS DUTY: missing target unit context")
                return False
            try:
                army = self.player.get_army()
            except Exception:
                raise
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if sm_mgr is None or not getattr(sm_mgr, "is_rage_cursed_onslaught", lambda: False)():
                return False
            try:
                if not unit.has_any_keyword("DEATH COMPANY"):
                    return False
            except Exception:
                raise
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "fight phase":
                print("ERROR: DEATHLESS DUTY: wrong phase")
                return False
            if candidates:
                try:
                    if unit not in list(candidates or []):
                        print("ERROR: DEATHLESS DUTY: target was not selected by attacker")
                        return False
                except Exception:
                    raise
            try:
                if attacker_unit is not None and attacker_unit.get_parent_army().player is self.player:
                    print("ERROR: DEATHLESS DUTY: attacker is not enemy")
                    return False
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(unit):
                    print("ERROR: DEATHLESS DUTY: target cannot be selected")
                    return False
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=unit).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["deathless_duty_active"] = True
                sr["deathless_duty_expires_phase"] = "FIGHT_PHASE"
                sr["deathless_duty_source"] = s.name
                root.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: DEATHLESS DUTY: {getattr(root, 'name', 'Unit')} will fight on death after attacks resolve this phase.")
            return True

        # EMPEROR'S CHILDREN: DEATH ECSTASY
        if s.name.upper() == "DEATH ECSTASY":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            attacker_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
            candidates = list(kwargs.get("candidates") or kwargs.get("target_units") or [])
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "DEATH ECSTASY":
                        unit = unit or r.get("unit") or r.get("target_unit")
                        attacker_unit = attacker_unit or r.get("attacking_unit")
                        if not candidates:
                            candidates = list(r.get("candidates") or r.get("target_units") or [])
                        break
            if unit is None:
                print("ERROR: DEATH ECSTASY: missing target unit context")
                return False
            try:
                army = self.player.get_army()
            except Exception:
                raise
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is None or not getattr(mgr, "is_peerless_bladesmen", lambda: False)():
                return False
            try:
                if not mgr.is_emperors_children_unit(unit):
                    return False
            except Exception:
                raise
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "fight phase":
                print("ERROR: DEATH ECSTASY: wrong phase")
                return False
            if candidates:
                try:
                    if unit not in list(candidates or []):
                        print("ERROR: DEATH ECSTASY: target was not selected by attacker")
                        return False
                except Exception:
                    raise
            try:
                if attacker_unit is not None and attacker_unit.get_parent_army().player is self.player:
                    print("ERROR: DEATH ECSTASY: attacker is not enemy")
                    return False
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(unit):
                    print("ERROR: DEATH ECSTASY: target cannot be selected")
                    return False
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=unit).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["death_ecstasy_active"] = True
                sr["death_ecstasy_expires_phase"] = "FIGHT_PHASE"
                sr["death_ecstasy_source"] = s.name
                root.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: DEATH ECSTASY: {getattr(root, 'name', 'Unit')} will fight on death after attacks resolve this phase.")
            return True

        # EMPEROR'S CHILDREN: TERRIFYING SPECTACLE
        if s.name.upper() == "TERRIFYING SPECTACLE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                print("ERROR: TERRIFYING SPECTACLE: missing target unit context")
                return False
            try:
                army = self.player.get_army()
            except Exception:
                raise
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is None or not getattr(mgr, "is_peerless_bladesmen", lambda: False)():
                return False
            try:
                if not mgr.is_emperors_children_unit(unit):
                    return False
            except Exception:
                raise
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "command phase":
                print("ERROR: TERRIFYING SPECTACLE: wrong phase")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(unit):
                    print("ERROR: TERRIFYING SPECTACLE: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            sr_root = getattr(root, "special_rules", None)
            if not isinstance(sr_root, dict):
                sr_root = {}
            if not bool(sr_root.get("ec_last_turn_charged", False)) or not bool(sr_root.get("ec_last_turn_destroyed_enemy_in_fight", False)):
                print("ERROR: TERRIFYING SPECTACLE: target did not charge and destroy in previous turn")
                return False
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            game_map = getattr(self.game, "map", None)
            if game_map is None:
                return False
            try:
                enemy_units = list(game_map.get_enemy_units(root) or [])
            except Exception:
                enemy_units = []
            affected = []
            for enemy in enemy_units:
                try:
                    if enemy is None or not enemy.is_alive():
                        continue
                    if getattr(enemy, "deployed", True) is False:
                        continue
                    if getattr(enemy, "is_in_reserves", lambda: False)():
                        continue
                except Exception:
                    continue
                try:
                    dist = float(game_map.get_distance_between_units(root, enemy))
                except Exception:
                    continue
                if dist > 6.0:
                    continue
                affected.append(enemy)
            if not affected:
                print("ERROR: TERRIFYING SPECTACLE: no enemy units within 6\"")
                return False
            for enemy in affected:
                try:
                    sr = getattr(enemy, "special_rules", None)
                    if not isinstance(sr, dict):
                        sr = {}
                    if hasattr(enemy, "is_below_half_strength") and enemy.is_below_half_strength():
                        sr["battle_shock_test_modifier"] = int(sr.get("battle_shock_test_modifier", 0) or 0) - 1
                        sr.setdefault("battle_shock_test_modifier_reasons", []).append("Terrifying Spectacle (below half-strength)")
                    sr["battle_shock_suppress_other_tests_phase"] = "COMMAND_PHASE"
                    sr["battle_shock_suppress_other_tests_source"] = s.name
                    sr["battle_shock_allow_suppressed_test"] = True
                    enemy.special_rules = sr
                except Exception:
                    raise
                try:
                    enemy.take_battle_shock_test(int(getattr(self.game, "turn", 0) or 0))
                except Exception:
                    raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: TERRIFYING SPECTACLE: {len(affected)} enemy unit(s) tested for Battle-shock.")
            return True

        # EMPEROR'S CHILDREN: CUT DOWN THE WEAK
        if s.name.upper() == "CUT DOWN THE WEAK":
            enemy = kwargs.get("enemy_unit")
            candidates = list(kwargs.get("candidates") or [])
            if enemy is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "CUT DOWN THE WEAK":
                        enemy = r.get("enemy_unit") or enemy
                        if not candidates:
                            candidates = list(r.get("candidates") or [])
                        break
            if enemy is None:
                print("ERROR: CUT DOWN THE WEAK: no enemy unit context")
                return False
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None and candidates:
                unit = candidates[0]
            if unit is None:
                print("ERROR: CUT DOWN THE WEAK: no eligible unit selected")
                return False
            try:
                if unit.get_parent_army().player is not self.player:
                    print("ERROR: CUT DOWN THE WEAK: target unit does not belong to player")
                    return False
            except Exception:
                raise
            try:
                army = self.player.get_army()
            except Exception:
                raise
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is None or not getattr(mgr, "is_peerless_bladesmen", lambda: False)():
                return False
            try:
                if not mgr.is_emperors_children_unit(unit):
                    return False
            except Exception:
                raise
            try:
                if unit.has_keyword("Vehicle") and not unit.has_keyword("Walker"):
                    print("WARN: CUT DOWN THE WEAK: only WALKER vehicles can be selected")
                    return False
            except Exception:
                raise
            dist = None
            try:
                if self.game and getattr(self.game, "map", None):
                    dist = self.game.map.get_distance_between_units(unit, enemy)
            except Exception:
                raise
            if dist is None or dist > 6.0:
                print("ERROR: CUT DOWN THE WEAK: target not within 6\" of enemy")
                return False
            try:
                if not unit.can_declare_charge_against(enemy, self.game, out_of_turn=True):
                    print("ERROR: CUT DOWN THE WEAK: target cannot declare charge against enemy")
                    return False
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=unit).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            ok = False
            try:
                ok = bool(self.game.attempt_charge(unit, enemy, out_of_turn=True, count_as_charged=False))
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            if not ok:
                print("ERROR: CUT DOWN THE WEAK: charge failed")
            return True

        # Special-case: NEW ORDERS (discard one active Secondary and draw a new one)
        if s.name.upper() == "NEW ORDERS":
            # Must be your Command phase end; we gate to Command phase + your turn via is_phase_allowed/is_turn_allowed
            # Additional availability: need an active secondary and at least one card to draw
            player_obj = self.player
            if not getattr(player_obj, 'active_secondaries', None):
                print("ERROR: New Orders: no active Secondary to discard")
                return False
            if not player_obj.can_draw_secondary():
                print("ERROR: New Orders: no Secondary cards left to draw")
                return False
            # Choose target card (allow UI to pass one)
            target_card = kwargs.get('secondary_card')
            if target_card is None:
                # Default heuristic: discard the first active
                try:
                    target_card = player_obj.active_secondaries[0]
                except Exception:
                    raise
            if target_card is None or target_card not in player_obj.active_secondaries:
                print("ERROR: New Orders: invalid or missing target Secondary card")
                return False
            # Spend CP per stratagem cost
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            # Discard chosen card and draw back up to two
            try:
                name = getattr(target_card, 'name', 'Secondary')
                print(f"INFO: New Orders: discarding '{name}' and drawing a new Secondary")
            except Exception:
                raise
            player_obj.discard_secondary(target_card, gain_cp=False)
            player_obj.draw_secondary_until_two(self.game)
            if kwargs.get('dequeue') is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            return True

        # Special-case: RAPID INGRESS (arrive from reserves at end of opponent's Movement phase)
        if s.name.upper() == "RAPID INGRESS":
            # Choose target unit
            target = kwargs.get("unit") or kwargs.get("target_unit")
            if target is None:
                # Try candidates from queued reaction context
                cand = kwargs.get("candidates") or []
                if cand:
                    # Prefer Deep Strike units (non-strategic reserves) first
                    try:
                        target = next((u for u in cand if not getattr(u, "is_in_strategic_reserves", lambda: False)()), cand[0])
                    except Exception:
                        raise
            if target is None:
                print("ERROR: Rapid Ingress: no target unit provided")
                return False
            # Validate ownership + reserves status
            try:
                if target.get_parent_army().player is not self.player:
                    print("ERROR: Rapid Ingress: target unit does not belong to player")
                    return False
            except Exception:
                raise
            if not getattr(target, "is_in_reserves", lambda: False)():
                print("ERROR: Rapid Ingress: target unit is not in reserves")
                return False
            # Cult Ambush restriction: cannot be targeted by Rapid Ingress.
            if bool(getattr(target, "_cult_ambush", False)):
                print("INFO: Rapid Ingress: target unit is in Cult Ambush")
                return False
            # Restriction: cannot arrive in a battle round it would not normally be able to
            if not getattr(target, "can_arrive_from_reserves", lambda _t: False)(getattr(self.game, "turn", 0)):
                print("ERROR: Rapid Ingress: target unit cannot arrive from reserves this battle round")
                return False
            # Determine placement
            position = kwargs.get("position")
            if position is None:
                try:
                    position = self.game.find_valid_reserves_position(target) if hasattr(self.game, "find_valid_reserves_position") else None
                except Exception:
                    raise
            if not position:
                print("ERROR: Rapid Ingress: could not find a valid placement position")
                return False
            # Attempt arrival
            try:
                ok = target.arrive_from_reserves(position, getattr(self.game, "turn", 0), getattr(self.game, "map", None))
            except Exception as e:
                raise
            if not ok:
                print("ERROR: Rapid Ingress: arrival failed")
                return False
            # Add to map unit list if needed
            try:
                if hasattr(self.game, "map") and hasattr(self.game.map, "units"):
                    if target not in self.game.map.units:
                        self.game.map.units.append(target)
            except Exception:
                raise
            # Spend CP (after success to avoid consuming CP on placement failure)
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                print("ERROR: Rapid Ingress succeeded but CP spend failed; adjusting CP manually")
            print(f"INFO: Rapid Ingress: {target.name} arrived from reserves")
            if kwargs.get('dequeue') is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            return True

        # Core: GO TO GROUND
        if s.name.upper() == "GO TO GROUND":
            target = kwargs.get("unit") or kwargs.get("target_unit")
            if target is None:
                cand = kwargs.get("candidates") or []
                if cand:
                    target = cand[0]
            if target is None:
                print("ERROR: GO TO GROUND: no target unit provided")
                return False
            # Spend CP
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            # Mark active until end of Shooting phase; cleared in _on_phase_end.
            try:
                sr = getattr(target, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["go_to_ground_active"] = True
                target.special_rules = sr
                print(f"INFO: GO TO GROUND used on {getattr(target, 'name', 'Unit')}: Benefit of Cover + 6++ until end of phase")
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            return True

        # Core: GRENADE
        if s.name.upper() == "GRENADE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            enemy = kwargs.get("enemy_unit")

            def _grenade_unit_eligible(u) -> bool:
                try:
                    if u is None or not u.is_alive() or not getattr(u, "deployed", False):
                        return False
                    if not u.has_keyword("Grenades"):
                        return False
                    rs = getattr(u, "round_state", None)
                    if (
                        getattr(rs, "advanced_this_round", False)
                        or getattr(rs, "fell_back_this_round", False)
                        or getattr(rs, "shot_this_round", False)
                    ):
                        return False
                    if self.game and getattr(self.game, "map", None):
                        if any(
                            self.game.map.is_within_engagement_range(u, e)
                            for e in (self.game.map.get_enemy_units(u) or [])
                            if e.is_alive()
                        ):
                            return False
                except Exception:
                    raise
                return True

            if unit is None:
                # Best-effort pick: first eligible GRENADES unit from your army
                for u in list(getattr(self.player.get_army(), "units", []) or []):
                    if _grenade_unit_eligible(u):
                        unit = u
                        break
            if unit is None:
                print("ERROR: GRENADE: no eligible friendly GRENADES unit")
                return False
            if not _grenade_unit_eligible(unit):
                print("ERROR: GRENADE: selected unit is not eligible (already shot/advanced/fell back/engaged or no Grenades)")
                return False
            if enemy is None and self.game and getattr(self.game, "map", None):
                # Best-effort: pick the first eligible enemy within 8" and visible, and not in engagement range of any friendly unit.
                try:
                    enemies = list(self.game.map.get_enemy_units(unit)) or []
                except Exception:
                    raise
                for e in enemies:
                    try:
                        if e is None or not e.is_alive():
                            continue
                        # Enemy must not be within engagement range of any friendly unit
                        ok = True
                        for f in list(getattr(self.player.get_army(), "units", []) or []):
                            if f is None or not getattr(f, "deployed", False) or not f.is_alive():
                                continue
                            if self.game.map.is_within_engagement_range(f, e):
                                ok = False
                                break
                        if not ok:
                            continue
                        if self.game.map.get_distance_between_units(unit, e) > 8.0:
                            continue
                        # Visibility: any model in unit can see any model in enemy
                        vis = False
                        for m in (unit.get_models_for_collision() or []):
                            if not getattr(m, "is_alive", False):
                                continue
                            for tm in (e.get_models_for_collision() or []):
                                if not getattr(tm, "is_alive", False):
                                    continue
                                if self.game.map.can_model_see_model(m, tm):
                                    vis = True
                                    break
                            if vis:
                                break
                        if not vis:
                            continue
                        enemy = e
                        break
                    except Exception:
                        raise
            if enemy is None:
                print("ERROR: GRENADE: no eligible enemy target found/provided")
                return False
            # Spend CP
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            # Roll 6D6; each 4+ = 1 mortal wound
            rolls = [dice_module.get_roll("D6") for _ in range(6)]
            mw = sum(1 for r in rolls if int(r) >= 4)
            try:
                print(f"INFO: GRENADE: rolls={rolls} -> {mw} mortal wounds to {enemy.name}")
            except Exception:
                raise
            if mw > 0:
                try:
                    unit._apply_mortal_wounds_to_unit(enemy, int(mw), game_map=getattr(self.game, "map", None))
                except Exception:
                    raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            return True

        # Core: TANK SHOCK
        if s.name.upper() == "TANK SHOCK":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            enemy = kwargs.get("enemy_unit")
            eligible_enemies = kwargs.get("eligible_enemy_units") or []
            if unit is None:
                print("ERROR: TANK SHOCK: no charging VEHICLE unit provided")
                return False
            if not bool(getattr(unit, "is_vehicle", False)):
                print("ERROR: TANK SHOCK: target unit is not a VEHICLE")
                return False
            if enemy is None:
                enemy = eligible_enemies[0] if eligible_enemies else None
            if enemy is None and self.game and getattr(self.game, "map", None):
                try:
                    for e in (self.game.map.get_enemy_units(unit) or []):
                        if e is None or not e.is_alive():
                            continue
                        if self.game.map.is_within_engagement_range(unit, e):
                            enemy = e
                            break
                except Exception:
                    raise
            if enemy is None:
                print("ERROR: TANK SHOCK: no enemy unit in Engagement Range")
                return False
            # Spend CP
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            # Pick a VEHICLE model in your unit within ER of that enemy unit.
            chosen_model = None
            try:
                from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
                for m in unit.get_models_for_collision():
                    if not getattr(m, "is_alive", False):
                        continue
                    for tm in enemy.get_models_for_collision():
                        if not getattr(tm, "is_alive", False):
                            continue
                        hd = float(horizontal_distance_between_bases_2d(m.model_base, tm.model_base))
                        vd = float(vertical_distance_between_bases(m.model_base, tm.model_base))
                        if hd <= ENGAGEMENT_RANGE_HORIZONTAL and vd <= ENGAGEMENT_RANGE_VERTICAL:
                            chosen_model = m
                            break
                    if chosen_model is not None:
                        break
            except Exception:
                raise
            if chosen_model is None:
                try:
                    chosen_model = next(m for m in unit.get_models_for_collision() if getattr(m, "is_alive", False))
                except Exception:
                    raise
            if chosen_model is None:
                print("ERROR: TANK SHOCK: no alive VEHICLE model found")
                return False
            try:
                tval = int(getattr(chosen_model, "toughness", getattr(unit, "toughness", 0)) or 0)
            except Exception:
                raise
            if tval <= 0:
                print("ERROR: TANK SHOCK: could not determine Toughness for VEHICLE model")
                return False
            rolls = [dice_module.get_roll("D6") for _ in range(int(tval))]
            mw = min(6, sum(1 for r in rolls if int(r) >= 5))
            try:
                print(f"INFO: TANK SHOCK: rolls={rolls} (T{tval}) -> {mw} mortal wounds to {enemy.name}")
            except Exception:
                raise
            if mw > 0:
                try:
                    unit._apply_mortal_wounds_to_unit(enemy, int(mw), game_map=getattr(self.game, "map", None))
                except Exception:
                    raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            return True

        # Core: HEROIC INTERVENTION
        if s.name.upper() == "HEROIC INTERVENTION":
            enemy = kwargs.get("enemy_unit")
            candidates = list(kwargs.get("candidates") or [])
            if enemy is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").upper() == "HEROIC INTERVENTION":
                        enemy = r.get("enemy_unit") or enemy
                        if not candidates:
                            candidates = list(r.get("candidates") or [])
                        break
            if enemy is None:
                print("ERROR: Heroic Intervention: no enemy unit context")
                return False

            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None and candidates:
                unit = candidates[0]
            if unit is None:
                print("ERROR: Heroic Intervention: no eligible unit selected")
                return False

            try:
                if unit.get_parent_army().player is not self.player:
                    print("ERROR: Heroic Intervention: target unit does not belong to player")
                    return False
            except Exception:
                raise
            try:
                if unit.has_keyword("Vehicle") and not unit.has_keyword("Walker"):
                    print("WARN: Heroic Intervention: only WALKER vehicles can be selected")
                    return False
            except Exception:
                raise
            dist = None
            try:
                if self.game and getattr(self.game, "map", None):
                    dist = self.game.map.get_distance_between_units(unit, enemy)
            except Exception:
                raise
            if dist is None or dist > 6.0:
                print("ERROR: Heroic Intervention: target not within 6\" of enemy")
                return False

            try:
                if not unit.can_declare_charge_against(enemy, self.game, out_of_turn=True):
                    print("ERROR: Heroic Intervention: target cannot declare charge against enemy")
                    return False
            except Exception:
                raise
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False

            ok = False
            try:
                ok = bool(self.game.attempt_charge(unit, enemy, out_of_turn=True, count_as_charged=False))
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
                self._record_heroic_intervention_use(unit)
            except Exception:
                raise
            if not ok:
                print("ERROR: Heroic Intervention: charge failed")
            return True

        # Berzerker Warband: APOPLETIC FRENZY (advance and charge for Khorne Berzerkers)
        if s.name.upper() == "APOPLECTIC FRENZY":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "APOPLECTIC FRENZY":
                        unit = r.get("unit") or r.get("target_unit")
                        if unit is not None:
                            kwargs.setdefault("action", r.get("action"))
                        break
            if unit is None:
                print("ERROR: Apoplectic Frenzy: no target unit provided")
                return False
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_berzerker_warband", lambda: False)():
                return False
            # Timing: your Movement phase, just after selecting to Advance.
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "movement phase":
                print("ERROR: Apoplectic Frenzy: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is not self.player:
                print("ERROR: Apoplectic Frenzy: not your turn")
                return False
            if str(kwargs.get("action", "") or "").strip().lower() not in ("", "advance"):
                print("ERROR: Apoplectic Frenzy: invalid trigger")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(unit):
                    print("ERROR: Apoplectic Frenzy: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not (unit.has_keyword("KHORNE") and unit.has_keyword("BERZERKERS")):
                    print("ERROR: Apoplectic Frenzy: target is not KHORNE BERZERKERS")
                    return False
            except Exception:
                raise
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["apoplectic_frenzy_active"] = True
                sr["apoplectic_frenzy_turn"] = int(getattr(self.game, "turn", 0) or 0)
                unit.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: APOPLETIC FRENZY: {getattr(unit, 'name', 'Unit')} can charge after advancing this turn.")
            return True

        # Rage-cursed Onslaught: RED WRATH (advance then shoot/charge choice; Red Thirst for both)
        if s.name.upper() == "RED WRATH":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "RED WRATH":
                        unit = r.get("unit") or r.get("target_unit")
                        if unit is not None:
                            kwargs.setdefault("action", r.get("action"))
                        break
            if unit is None:
                print("ERROR: RED WRATH: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            try:
                army = root.get_parent_army()
            except Exception:
                raise
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if sm_mgr is None or not getattr(sm_mgr, "is_rage_cursed_onslaught", lambda: False)():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "movement phase":
                print("ERROR: RED WRATH: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is not self.player:
                print("ERROR: RED WRATH: not your turn")
                return False
            if str(kwargs.get("action", "") or "").strip().lower() not in ("", "advance"):
                print("ERROR: RED WRATH: invalid trigger")
                return False
            try:
                if not bool(getattr(getattr(root, "round_state", None), "advanced_this_round", False)):
                    print("ERROR: RED WRATH: unit did not Advance")
                    return False
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: RED WRATH: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.has_any_keyword("BLOOD ANGELS"):
                    print("ERROR: RED WRATH: target is not BLOOD ANGELS")
                    return False
            except Exception:
                raise
            mode = kwargs.get("mode") or kwargs.get("red_wrath_mode") or kwargs.get("choice")
            if isinstance(mode, dict):
                mode = mode.get("mode") or mode.get("choice")
            mode = str(mode or "").strip().lower()
            if mode in ("shoot", "shoot_only"):
                choice = "shoot"
                red_thirst = False
            elif mode in ("charge", "charge_only"):
                choice = "charge"
                red_thirst = False
            elif mode in ("both", "shoot_and_charge", "shoot+charge", "red_thirst", "red thirst"):
                choice = "both"
                red_thirst = True
            else:
                print("ERROR: RED WRATH: missing or invalid choice")
                return False
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["red_wrath_mode"] = choice
                sr["red_wrath_turn_owner"] = str(getattr(self.player, "id", "") or "")
                sr["red_wrath_turn"] = int(getattr(self.game, "turn", 0) or 0)
                sr["red_wrath_source"] = s.name
                root.special_rules = sr
            except Exception:
                raise
            if red_thirst:
                try:
                    from ..units.status_effects import BattleShockEffect
                    if hasattr(root, "is_battle_shocked") and callable(root.is_battle_shocked):
                        if not bool(root.is_battle_shocked()):
                            current_turn = int(getattr(self.game, "turn", 1) or 1) if self.game is not None else 1
                            root.apply_status_effect(BattleShockEffect(current_turn))
                except Exception:
                    raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            if choice == "both":
                print(f"INFO: RED WRATH: {getattr(root, 'name', 'Unit')} can shoot and charge after advancing this turn.")
            else:
                print(f"INFO: RED WRATH: {getattr(root, 'name', 'Unit')} can {choice} after advancing this turn.")
            return True

        # Warhost: BLITZING FIREPOWER
        if s.name.upper() == "BLITZING FIREPOWER":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                cand = kwargs.get("candidates") or []
                if cand:
                    unit = cand[0]
            if unit is None:
                print("ERROR: Blitzing Firepower: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if not self._is_warhost_detachment():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "shooting phase":
                print("ERROR: Blitzing Firepower: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is not self.player:
                print("ERROR: Blitzing Firepower: not your turn")
                return False
            try:
                if not root.is_alive():
                    return False
            except Exception:
                raise
            try:
                if not getattr(root, "deployed", False):
                    return False
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    return False
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: Blitzing Firepower: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.has_any_keyword("ASURYANI"):
                    return False
            except Exception:
                raise
            try:
                if getattr(getattr(root, "round_state", None), "shot_this_round", False):
                    return False
            except Exception:
                raise
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["blitzing_firepower_active"] = True
                sr["blitzing_firepower_expires_phase"] = "SHOOTING_PHASE"
                root.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: BLITZING FIREPOWER: {getattr(root, 'name', 'Unit')} gains Sustained Hits vs targets within 12\".")
            return True

        # Warhost: FEIGNED RETREAT
        if s.name.upper() == "FEIGNED RETREAT":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "FEIGNED RETREAT":
                        unit = r.get("unit") or r.get("target_unit")
                        if unit is not None:
                            kwargs.setdefault("action", r.get("action"))
                        break
            if unit is None:
                print("ERROR: Feigned Retreat: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if not self._is_warhost_detachment():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "movement phase":
                print("ERROR: Feigned Retreat: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is not self.player:
                print("ERROR: Feigned Retreat: not your turn")
                return False
            if str(kwargs.get("action", "") or "").strip().lower() not in ("", "fall_back"):
                print("ERROR: Feigned Retreat: invalid trigger")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: Feigned Retreat: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.has_any_keyword("ASURYANI"):
                    return False
            except Exception:
                raise
            try:
                if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                    return False
            except Exception:
                raise
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["feigned_retreat_active"] = True
                sr["feigned_retreat_turn_owner"] = str(getattr(self.player, "id", "") or "")
                sr["feigned_retreat_turn"] = int(getattr(self.game, "turn", 0) or 0)
                root.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: FEIGNED RETREAT: {getattr(root, 'name', 'Unit')} can shoot and charge after falling back.")
            return True

        # Warhost: FIRE AND FADE
        if s.name.upper() == "FIRE AND FADE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "FIRE AND FADE":
                        unit = r.get("unit") or r.get("target_unit")
                        break
            if unit is None:
                print("ERROR: Fire and Fade: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if not self._is_warhost_detachment():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "shooting phase":
                print("ERROR: Fire and Fade: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is not self.player:
                print("ERROR: Fire and Fade: not your turn")
                return False
            try:
                if not root.is_alive():
                    return False
            except Exception:
                raise
            try:
                if not getattr(root, "deployed", False):
                    return False
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    return False
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: Fire and Fade: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.has_any_keyword("ASURYANI"):
                    return False
                if not root.has_keyword("INFANTRY"):
                    return False
                if root.has_keyword("WRAITH CONSTRUCT"):
                    return False
                if root.has_keyword("AIRCRAFT") or bool(getattr(root, "is_aircraft", False)):
                    return False
                if str(getattr(root, "name", "") or "").strip().upper() == "ASURMEN":
                    return False
            except Exception:
                raise
            try:
                if not bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                    return False
            except Exception:
                raise
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                roll = int(dice_module.get_roll("D6") or 0)
            except Exception:
                raise
            move_max = int(roll) + 1
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["fire_and_fade_no_charge_turn_owner"] = str(getattr(self.player, "id", "") or "")
                sr["fire_and_fade_no_charge_turn"] = int(getattr(self.game, "turn", 0) or 0)
                sr["fire_and_fade_no_embark_turn_owner"] = str(getattr(self.player, "id", "") or "")
                sr["fire_and_fade_no_embark_turn"] = int(getattr(self.game, "turn", 0) or 0)
                root.special_rules = sr
            except Exception:
                raise
            req = None
            try:
                if self.game is not None:
                    req = self.game._queue_reactive_move_movement_decision(
                        player=self.player,
                        unit=root,
                        max_distance=int(move_max),
                        kind="fire_and_fade",
                        movement_type="reactive",
                        source=s.name,
                    )
            except Exception:
                raise
            try:
                if req is not None and self.game is not None and hasattr(self.game, "event_system"):
                    self.game.event_system.publish(
                        "fire_and_fade_move",
                        player=self.player,
                        unit=root,
                        max_distance=int(move_max),
                        decision_request=req,
                    )
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"ERROR: FIRE AND FADE: {getattr(root, 'name', 'Unit')} can move {move_max}\" and cannot charge or embark this turn.")
            return True

        # Warhost: LIGHTNING-FAST REACTIONS
        if s.name.upper() == "LIGHTNING-FAST REACTIONS":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "LIGHTNING-FAST REACTIONS":
                        unit = r.get("unit") or r.get("target_unit")
                        break
            if unit is None:
                print("ERROR: Lightning-Fast Reactions: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if not self._is_warhost_detachment():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            pname = str(phase_name or "").strip().lower()
            if pname not in ("shooting phase", "fight phase"):
                print("ERROR: Lightning-Fast Reactions: wrong phase")
                return False
            if pname == "shooting phase":
                active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
                if active_player is self.player:
                    print("ERROR: Lightning-Fast Reactions: not opponent's Shooting phase")
                    return False
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: Lightning-Fast Reactions: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.has_any_keyword("ASURYANI"):
                    return False
                if root.has_keyword("WRAITH CONSTRUCT"):
                    return False
            except Exception:
                raise
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["lightning_fast_reactions_active"] = True
                sr["lightning_fast_reactions_expires_phase"] = "SHOOTING_PHASE" if pname == "shooting phase" else "FIGHT_PHASE"
                root.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: LIGHTNING-FAST REACTIONS: {getattr(root, 'name', 'Unit')} is harder to hit this phase.")
            return True

        # Warhost: SKYBORNE SANCTUARY
        if s.name.upper() == "SKYBORNE SANCTUARY":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            transport_unit = kwargs.get("transport_unit") or kwargs.get("transport")
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "SKYBORNE SANCTUARY":
                        unit = r.get("unit") or r.get("target_unit")
                        if transport_unit is None:
                            transport_unit = r.get("transport_unit") or r.get("transport")
                        break
            if unit is None:
                print("WARN: Skyborne Sanctuary: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if not self._is_warhost_detachment():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "fight phase":
                print("WARN: Skyborne Sanctuary: wrong phase")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("WARN: Skyborne Sanctuary: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.has_any_keyword("ASURYANI"):
                    return False
            except Exception:
                raise
            try:
                if not root.is_alive():
                    return False
            except Exception:
                raise
            try:
                if not getattr(root, "deployed", False):
                    return False
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    return False
            except Exception:
                raise
            try:
                sr = getattr(root, "special_rules", None)
                owner = str(sr.get("fire_and_fade_no_embark_turn_owner", "") or "") if isinstance(sr, dict) else ""
                turn = int(sr.get("fire_and_fade_no_embark_turn", 0) or 0) if isinstance(sr, dict) else 0
                if owner and self.game is not None:
                    if owner == str(getattr(getattr(self.game, "get_current_player", lambda: None)(), "id", "") or ""):
                        if int(getattr(self.game, "turn", 0) or 0) == int(turn or 0):
                            print("WARN: Skyborne Sanctuary: unit cannot embark this turn (Fire and Fade)")
                            return False
            except Exception:
                raise
            try:
                game_map = getattr(self.game, "map", None)
                engaged = False
                for enemy in list(game_map.get_enemy_units(root) or []):
                    if not getattr(enemy, "is_alive", lambda: True)():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    if game_map.is_within_engagement_range(root, enemy):
                        engaged = True
                        break
                if engaged:
                    return False
            except Exception:
                raise
            if transport_unit is None:
                try:
                    mapping = kwargs.get("transport_candidates_by_unit") or {}
                    transport_unit = (mapping.get(root) or [None])[0]
                except Exception:
                    raise
            if transport_unit is None:
                try:
                    transports = self._skyborne_transport_candidates(root)
                    if transports:
                        transport_unit = transports[0]
                except Exception:
                    raise
            if transport_unit is None:
                print("WARN: Skyborne Sanctuary: no transport provided")
                return False
            try:
                if not transport_unit.is_alive():
                    return False
            except Exception:
                raise
            try:
                if not getattr(transport_unit, "deployed", False):
                    return False
            except Exception:
                raise
            try:
                if not transport_unit.can_transport(root):
                    return False
            except Exception:
                raise
            try:
                from ..utility.aura_utils import unit_wholly_within_range_of_unit
                if not unit_wholly_within_range_of_unit(transport_unit, root, 6.0, use_attached_aggregate=True):
                    return False
            except Exception:
                raise
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                game_map = getattr(self.game, "map", None)
                if game_map is None:
                    raise RuntimeError("Skyborne Sanctuary requires an active game map.")
                if not transport_unit.add_passenger(root, game_map=game_map):
                    print("WARN: Skyborne Sanctuary: embark failed")
                    return False
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: Skyborne Sanctuary: {getattr(root, 'name', 'Unit')} embarked within {getattr(transport_unit, 'name', 'Transport')}.")
            return True

        # Warhost: WEBWAY TUNNEL
        if s.name.upper() == "WEBWAY TUNNEL":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "WEBWAY TUNNEL":
                        unit = r.get("unit") or r.get("target_unit")
                        break
            if unit is None:
                print("WARN: Webway Tunnel: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if not self._is_warhost_detachment():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "fight phase":
                print("ERROR: Webway Tunnel: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is self.player:
                print("ERROR: Webway Tunnel: not opponent's Fight phase")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: Webway Tunnel: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.has_any_keyword("ASURYANI"):
                    return False
                if not root.has_keyword("INFANTRY"):
                    return False
            except Exception:
                raise
            try:
                if not root.is_alive():
                    return False
            except Exception:
                raise
            try:
                if not getattr(root, "deployed", False):
                    return False
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    return False
            except Exception:
                raise
            try:
                game_map = getattr(self.game, "map", None)
                engaged = False
                for enemy in list(game_map.get_enemy_units(root) or []):
                    if not getattr(enemy, "is_alive", lambda: True)():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    if game_map.is_within_engagement_range(root, enemy):
                        engaged = True
                        break
                if engaged:
                    return False
            except Exception:
                raise
            if not self._unit_wholly_within_battlefield_edge_distance(root, 9.0):
                return False
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                game_map = getattr(self.game, "map", None)
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                raise
            for member in members:
                try:
                    if hasattr(member, "set_reserve_status"):
                        member.set_reserve_status("strategic_reserves")
                    else:
                        member.reserve_status = "strategic_reserves"
                except Exception:
                    raise
                try:
                    if hasattr(member, "mark_entered_reserves_midgame"):
                        member.mark_entered_reserves_midgame(game=self.game)
                except Exception:
                    raise
                try:
                    if bool(getattr(member, "is_aircraft", False)) and not bool(getattr(member, "hover_mode", False)):
                        if self.game is not None:
                            member._aircraft_return_turn = int(getattr(self.game, "turn", 0) or 0) + 1
                except Exception:
                    raise
                try:
                    member.deployed = True
                    member.reserve_turn_deployed = None
                    member.arrived_from_reserves_this_turn = False
                except Exception:
                    raise
                try:
                    if game_map is not None and hasattr(game_map, "units") and member in game_map.units:
                        game_map.units.remove(member)
                except Exception:
                    raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: Webway Tunnel: {getattr(root, 'name', 'Unit')} placed into Strategic Reserves.")
            return True

        # Berzerker Warband: BERZERKER'S WRATH (fixed 8" Blood Surge for Khorne Berzerkers)
        if s.name.upper() in ("BERZERKER\u2019S WRATH", "BERZERKER'S WRATH"):
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            attacker_unit = kwargs.get("attacker_unit")
            if unit is None or attacker_unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() in ("BERZERKER\u2019S WRATH", "BERZERKER'S WRATH"):
                        unit = unit or r.get("unit") or r.get("target_unit")
                        attacker_unit = attacker_unit or r.get("attacker_unit")
                        break
            if unit is None or attacker_unit is None:
                print("ERROR: Berzerker's Wrath: missing target context")
                return False
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_berzerker_warband", lambda: False)():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "shooting phase":
                print("ERROR: Berzerker's Wrath: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is self.player:
                print("ERROR: Berzerker's Wrath: not opponent's turn")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(unit):
                    print("ERROR: Berzerker's Wrath: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not (unit.has_keyword("KHORNE") and unit.has_keyword("BERZERKERS")):
                    print("ERROR: Berzerker's Wrath: target is not KHORNE BERZERKERS")
                    return False
            except Exception:
                raise
            try:
                if not unit.can_blood_surge(game=self.game, game_map=getattr(self.game, "map", None)):
                    print("ERROR: Berzerker's Wrath: target cannot Blood Surge")
                    return False
            except Exception:
                raise
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["blood_surge_fixed_distance"] = 8
                sr["blood_surge_fixed_distance_phase_key"] = unit._blood_surge_phase_key(self.game)
                unit.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: BERZERKER'S WRATH: {getattr(unit, 'name', 'Unit')} will Blood Surge up to 8\".")
            return True

        # Khorne Daemonkin: DAEMONIC FURY (grant [LANCE], and [TWIN-LINKED] if Daemonic Rage active)
        if s.name.upper() == "DAEMONIC FURY":
            target_unit = kwargs.get("target_unit") or kwargs.get("unit") or kwargs.get("blood_legions_unit")
            we_unit = kwargs.get("world_eaters_unit") or kwargs.get("support_unit") or kwargs.get("we_unit")
            candidates = kwargs.get("candidates") or []
            if target_unit is None and candidates:
                target_unit = candidates[0]
            if target_unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "DAEMONIC FURY":
                        target_unit = r.get("target_unit") or r.get("unit")
                        we_unit = we_unit or r.get("world_eaters_unit")
                        break
            if target_unit is None:
                try:
                    army = self.player.get_army()
                except Exception:
                    raise
                if army is not None:
                    for u in list(getattr(army, "units", []) or []):
                        if u is None:
                            continue
                        try:
                            root = u.get_attached_unit_root()
                        except Exception:
                            raise
                        if root is None:
                            continue
                        try:
                            if not root.is_alive():
                                continue
                        except Exception:
                            raise
                        target_unit = root
                        break
            if target_unit is None:
                print("ERROR: Daemonic Fury: no target unit provided")
                return False
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                raise
            try:
                if target_root.get_parent_army().player is not self.player:
                    print("ERROR: Daemonic Fury: target unit is not yours")
                    return False
            except Exception:
                raise
            if we_unit is None:
                try:
                    army = target_root.get_parent_army()
                except Exception:
                    raise
                if army is not None and getattr(self.game, "map", None) is not None:
                    for u in list(getattr(army, "units", []) or []):
                        try:
                            root = u.get_attached_unit_root()
                        except Exception:
                            raise
                        if root is None or root is target_root:
                            continue
                        try:
                            if not root.is_alive():
                                continue
                        except Exception:
                            raise
                        try:
                            dist = self.game.map.get_distance_between_units(root, target_root)
                        except Exception:
                            raise
                        if dist is None or dist > 6.0:
                            continue
                        we_unit = root
                        break
            if we_unit is None:
                print("ERROR: Daemonic Fury: no WORLD EATERS unit within 6\"")
                return False
            try:
                we_root = we_unit.get_attached_unit_root()
            except Exception:
                raise
            try:
                if we_root.get_parent_army().player is not self.player:
                    print("ERROR: Daemonic Fury: support unit is not yours")
                    return False
            except Exception:
                raise
            try:
                army = target_root.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "fight phase":
                print("ERROR: Daemonic Fury: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is not self.player:
                print("ERROR: Daemonic Fury: not your turn")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(target_root):
                    print("ERROR: Daemonic Fury: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not we_mgr.unit_is_blood_legions(target_root):
                    print("ERROR: Daemonic Fury: target is not BLOOD LEGIONS")
                    return False
            except Exception:
                raise
            try:
                if not we_mgr.unit_is_world_eaters(we_root):
                    print("ERROR: Daemonic Fury: support unit is not WORLD EATERS")
                    return False
            except Exception:
                raise
            try:
                if not getattr(target_root, "deployed", False) or getattr(target_root, "is_in_reserves", lambda: False)():
                    print("ERROR: Daemonic Fury: target is not on battlefield")
                    return False
            except Exception:
                raise
            try:
                if not getattr(we_root, "deployed", False) or getattr(we_root, "is_in_reserves", lambda: False)():
                    print("ERROR: Daemonic Fury: support unit is not on battlefield")
                    return False
            except Exception:
                raise
            try:
                dist = self.game.map.get_distance_between_units(target_root, we_root) if self.game else None
            except Exception:
                raise
            if dist is None or dist > 6.0:
                print("ERROR: Daemonic Fury: units are not within 6\"")
                return False

            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=target_root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False

            try:
                sr = getattr(we_root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["daemonic_fury_lance_active"] = True
                sr["daemonic_fury_lance_turn_owner"] = str(getattr(self.player, "id", "") or "")
                sr["daemonic_fury_lance_turn"] = int(getattr(self.game, "turn", 0) or 0)
                if getattr(we_mgr, "is_blood_tithe_active", None) and we_mgr.is_blood_tithe_active("DAEMONIC_RAGE"):
                    sr["daemonic_fury_twin_linked_active"] = True
                    sr["daemonic_fury_twin_linked_expires_phase"] = "FIGHT_PHASE"
                we_root.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: DAEMONIC FURY: {getattr(we_root, 'name', 'Unit')} gains [LANCE] (and [TWIN-LINKED] if active).")
            return True

        # Khorne Daemonkin: BLESSING OF BURNING BLOOD (grant invulnerable save to targeted WORLD EATERS unit)
        if s.name.upper() == "BLESSING OF BURNING BLOOD":
            target_unit = kwargs.get("target_unit") or kwargs.get("unit") or kwargs.get("blood_legions_unit")
            we_unit = kwargs.get("world_eaters_unit") or kwargs.get("support_unit") or kwargs.get("we_unit")
            candidates = kwargs.get("candidates") or []
            if target_unit is None and candidates:
                target_unit = candidates[0]
            if target_unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "BLESSING OF BURNING BLOOD":
                        target_unit = r.get("target_unit") or r.get("unit")
                        we_unit = we_unit or r.get("world_eaters_unit")
                        break
            if target_unit is None or we_unit is None:
                print("ERROR: Blessing of Burning Blood: missing target context")
                return False
            try:
                target_root = target_unit.get_attached_unit_root()
            except Exception:
                raise
            try:
                we_root = we_unit.get_attached_unit_root()
            except Exception:
                raise
            try:
                if target_root.get_parent_army().player is not self.player:
                    print("ERROR: Blessing of Burning Blood: target unit is not yours")
                    return False
            except Exception:
                raise
            try:
                if we_root.get_parent_army().player is not self.player:
                    print("ERROR: Blessing of Burning Blood: affected unit is not yours")
                    return False
            except Exception:
                raise
            try:
                army = we_root.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() not in ("shooting phase", "fight phase"):
                print("ERROR: Blessing of Burning Blood: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is self.player:
                print("ERROR: Blessing of Burning Blood: not opponent's turn")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(target_root):
                    print("ERROR: Blessing of Burning Blood: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not we_mgr.unit_is_blood_legions(target_root):
                    print("ERROR: Blessing of Burning Blood: target is not BLOOD LEGIONS")
                    return False
            except Exception:
                raise
            try:
                if not we_mgr.unit_is_world_eaters(we_root):
                    print("ERROR: Blessing of Burning Blood: affected unit is not WORLD EATERS")
                    return False
            except Exception:
                raise
            try:
                dist = self.game.map.get_distance_between_units(target_root, we_root) if self.game else None
            except Exception:
                raise
            if dist is None or dist > 6.0:
                print("ERROR: Blessing of Burning Blood: units are not within 6\"")
                return False

            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=target_root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False

            inv_value = 5
            try:
                if getattr(we_mgr, "is_blood_tithe_active", None) and we_mgr.is_blood_tithe_active("BOON_OF_BLOOD"):
                    inv_value = 4
            except Exception:
                raise
            try:
                entry = {
                    "value": int(inv_value),
                    "attack_type": "any",
                    "attacker_key": None,
                    "expires_phase": self._phase_key_from_name(phase_name),
                    "source": str(s.name or "Blessing of Burning Blood"),
                }
                self._append_defensive_effect(we_root, "defensive_invuln_overrides", entry)
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: BLESSING OF BURNING BLOOD: {getattr(we_root, 'name', 'Unit')} gains {inv_value}++.")
            return True

        # Khorne Daemonkin: DAEMONTIDE (return destroyed BLOOD LEGIONS models)
        if s.name.upper() == "DAEMONTIDE":
            we_unit = kwargs.get("target_unit") or kwargs.get("unit") or kwargs.get("world_eaters_unit")
            bl_unit = kwargs.get("blood_legions_unit") or kwargs.get("support_unit") or kwargs.get("bl_unit")
            candidates = kwargs.get("candidates") or []
            if we_unit is None and candidates:
                we_unit = candidates[0]
            if we_unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "DAEMONTIDE":
                        we_unit = r.get("target_unit") or r.get("unit")
                        bl_unit = bl_unit or r.get("blood_legions_unit")
                        break
            if we_unit is None:
                print("ERROR: Daemontide: no WORLD EATERS unit provided")
                return False
            try:
                we_root = we_unit.get_attached_unit_root()
            except Exception:
                raise
            try:
                if we_root.get_parent_army().player is not self.player:
                    print("ERROR: Daemontide: target unit is not yours")
                    return False
            except Exception:
                raise
            if bl_unit is None:
                try:
                    army = we_root.get_parent_army()
                except Exception:
                    raise
                if army is not None and getattr(self.game, "map", None) is not None:
                    for u in list(getattr(army, "units", []) or []):
                        try:
                            root = u.get_attached_unit_root()
                        except Exception:
                            raise
                        if root is None:
                            continue
                        try:
                            if not root.is_alive():
                                continue
                        except Exception:
                            raise
                        try:
                            dist = self.game.map.get_distance_between_units(root, we_root)
                        except Exception:
                            raise
                        if dist is None or dist > 6.0:
                            continue
                        bl_unit = root
                        break
            if bl_unit is None:
                print("ERROR: Daemontide: no BLOOD LEGIONS unit within 6\"")
                return False
            try:
                bl_root = bl_unit.get_attached_unit_root()
            except Exception:
                raise
            try:
                if bl_root.get_parent_army().player is not self.player:
                    print("ERROR: Daemontide: support unit is not yours")
                    return False
            except Exception:
                raise
            try:
                army = we_root.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "command phase":
                print("ERROR: Daemontide: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is not self.player:
                print("ERROR: Daemontide: not your turn")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(we_root):
                    print("ERROR: Daemontide: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not we_mgr.unit_is_world_eaters(we_root):
                    print("ERROR: Daemontide: target is not WORLD EATERS")
                    return False
            except Exception:
                raise
            try:
                if not we_mgr.unit_is_blood_legions(bl_root):
                    print("ERROR: Daemontide: support unit is not BLOOD LEGIONS")
                    return False
            except Exception:
                raise
            try:
                dist = self.game.map.get_distance_between_units(bl_root, we_root) if self.game else None
            except Exception:
                raise
            if dist is None or dist > 6.0:
                print("ERROR: Daemontide: units are not within 6\"")
                return False

            amount = 0
            try:
                if bl_root.has_keyword("MOUNTED"):
                    amount = 1
                elif bl_root.has_keyword("BEAST"):
                    amount = int(dice_module.get_roll("D3") or 0)
                elif bl_root.has_keyword("INFANTRY"):
                    amount = int(dice_module.get_roll("D6") or 0)
                else:
                    print("ERROR: Daemontide: unsupported BLOOD LEGIONS unit type")
                    return False
            except Exception as exc:
                raise
            amount = max(0, int(amount or 0))

            try:
                from ..utility.event_bus import append_dice
                append_dice(self.player, f"Daemontide return: {amount}")
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=we_root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False

            returned = 0
            skip_character = False
            try:
                members = bl_root.get_attached_unit_members()
                skip_character = bool(len(list(members or [])) > 1)
            except Exception:
                raise
            try:
                returned = self._return_destroyed_models_full(
                    bl_root,
                    amount=amount,
                    game_map=getattr(self.game, "map", None),
                    skip_character=skip_character,
                )
            except Exception:
                raise
            print(f"INFO: DAEMONTIDE: {getattr(bl_root, 'name', 'Unit')} returns {returned} model(s).")

            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            return True

        # Khorne Daemonkin: A WORTHY SKULL (gain D3 BTP and optionally activate Blood Tithe)
        if s.name.upper() == "A WORTHY SKULL":
            unit = kwargs.get("unit") or kwargs.get("attacker_unit") or kwargs.get("target_unit")
            target_unit = kwargs.get("target_unit")
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "A WORTHY SKULL":
                        unit = r.get("unit") or r.get("attacker_unit") or r.get("target_unit")
                        target_unit = target_unit or r.get("target_unit")
                        break
            if unit is None or target_unit is None:
                print("WARN:O A Worthy Skull: missing target context")
                return False
            try:
                unit = unit.get_attached_unit_root()
            except Exception:
                raise
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "fight phase":
                print("WARN:O A Worthy Skull: wrong phase")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(unit):
                    print("WARN:O A Worthy Skull: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not we_mgr.unit_is_blood_tithe_eligible(unit):
                    print("WARN:O A Worthy Skull: unit not eligible for Blood Tithe")
                    return False
            except Exception:
                raise
            try:
                is_char = bool(target_unit.has_keyword("Character"))
                is_mon = bool(target_unit.has_keyword("Monster"))
                if not (is_char or is_mon):
                    print("WARN:O A Worthy Skull: target was not CHARACTER or MONSTER")
                    return False
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=unit).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False

            try:
                roll = int(dice_module.get_roll("D3") or 0)
            except Exception:
                raise
            if roll < 0:
                roll = 0
            total = we_mgr.add_blood_tithe_points(roll)
            try:
                es = getattr(self.game, "event_system", None)
                if es is not None:
                    es.publish(
                        "blood_tithe_points_gained",
                        player=getattr(army, "player", None) or self.player,
                        amount=int(roll),
                        total=int(total or 0),
                        attacker_unit=unit,
                        target_unit=target_unit,
                        roll=int(roll),
                    )
                    es.publish(
                        "blood_tithe_updated",
                        player=getattr(army, "player", None) or self.player,
                        total=int(total or 0),
                        active=[a.name for a in we_mgr.get_active_blood_tithe_abilities()],
                    )
            except Exception:
                raise
            try:
                if int(we_mgr.blood_tithe_points or 0) > 0:
                    we_mgr.prompt_blood_tithe_activation(
                        game=self.game,
                        player=self.player,
                        timing="fight_phase",
                        source="A Worthy Skull",
                        ignore_command_phase_limit=True,
                    )
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: A WORTHY SKULL: gained {int(roll)} Blood Tithe point(s).")
            return True

        # Berzerker Warband: HACK AND SLASH (+1 AP on melee weapons after charging)
        if s.name.upper() == "HACK AND SLASH":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                print("WARN:O Hack and Slash: no target unit provided")
                return False
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_berzerker_warband", lambda: False)():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "fight phase":
                print("WARN:O Hack and Slash: wrong phase")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(unit):
                    print("WARN:O Hack and Slash: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not (hasattr(unit, "has_any_keyword") and unit.has_any_keyword("WORLD EATERS")):
                    print("WARN:O Hack and Slash: target is not WORLD EATERS")
                    return False
            except Exception:
                raise
            try:
                charged = bool(getattr(getattr(unit, "round_state", None), "charged_this_round", False))
            except Exception:
                raise
            if not charged:
                print("WARN:O Hack and Slash: target did not charge this turn")
                return False
            try:
                if getattr(getattr(unit, "round_state", None), "fought_this_phase", False):
                    print("WARN:O Hack and Slash: target already fought this phase")
                    return False
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=unit).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["hack_and_slash_active"] = True
                sr["hack_and_slash_ap_bonus"] = 1
                sr["hack_and_slash_expires_phase"] = "FIGHT_PHASE"
                unit.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: HACK AND SLASH: {getattr(unit, 'name', 'Unit')} gains +1 AP on melee weapons this phase.")
            return True

        # Rage-cursed Onslaught: LIMB FROM LIMB (+1 S or +1 AP, or Red Thirst for both + Battle-shock)
        if s.name.upper() == "LIMB FROM LIMB":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                print("ERROR: LIMB FROM LIMB: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            try:
                army = root.get_parent_army()
            except Exception:
                raise
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if sm_mgr is None or not getattr(sm_mgr, "is_rage_cursed_onslaught", lambda: False)():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "fight phase":
                print("ERROR: LIMB FROM LIMB: wrong phase")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: LIMB FROM LIMB: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.has_any_keyword("BLOOD ANGELS"):
                    print("ERROR: LIMB FROM LIMB: target is not BLOOD ANGELS")
                    return False
            except Exception:
                raise
            try:
                charged = bool(getattr(getattr(root, "round_state", None), "charged_this_round", False))
            except Exception:
                raise
            if not charged:
                print("ERROR: LIMB FROM LIMB: target did not charge this turn")
                return False
            choice = kwargs.get("choice") or kwargs.get("limb_from_limb_choice")
            if isinstance(choice, dict):
                choice = choice.get("choice") or choice.get("mode")
            choice = str(choice or "").strip().lower()
            s_bonus = 0
            ap_bonus = 0
            red_thirst = False
            if choice in ("strength", "str", "s"):
                s_bonus = 1
            elif choice in ("ap", "armour_penetration", "armor_penetration"):
                ap_bonus = 1
            elif choice in ("red_thirst", "red thirst", "both", "strength_and_ap"):
                s_bonus = 1
                ap_bonus = 1
                red_thirst = True
            else:
                print("ERROR: LIMB FROM LIMB: missing or invalid choice")
                return False
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["limb_from_limb_melee_strength_bonus"] = int(s_bonus)
                sr["limb_from_limb_melee_ap_bonus"] = int(ap_bonus)
                sr["limb_from_limb_expires_phase"] = "FIGHT_PHASE"
                sr["limb_from_limb_source"] = s.name
                root.special_rules = sr
            except Exception:
                raise
            if red_thirst:
                try:
                    from ..units.status_effects import BattleShockEffect
                    if hasattr(root, "is_battle_shocked") and callable(root.is_battle_shocked):
                        if not bool(root.is_battle_shocked()):
                            current_turn = int(getattr(self.game, "turn", 1) or 1) if self.game is not None else 1
                            root.apply_status_effect(BattleShockEffect(current_turn))
                except Exception:
                    raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            if red_thirst:
                print(f"INFO: LIMB FROM LIMB: {getattr(root, 'name', 'Unit')} gains +1S and +1 AP (Red Thirst) this phase.")
            elif s_bonus:
                print(f"INFO: LIMB FROM LIMB: {getattr(root, 'name', 'Unit')} gains +1 Strength this phase.")
            else:
                print(f"INFO: LIMB FROM LIMB: {getattr(root, 'name', 'Unit')} gains +1 AP this phase.")
            return True

        # Generic: +AP on melee weapons for a unit that charged and has not fought yet (e.g., CRUEL BLADESMAN).
        spec = self._get_charge_melee_ap_spec(s)
        if spec:
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                print(f"ERROR: {s.name}: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if "fight" not in str(phase_name or "").strip().lower():
                print(f"ERROR: {s.name}: wrong phase")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print(f"ERROR: {s.name}: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not self._unit_matches_defensive_target_spec(root, spec):
                    print(f"ERROR: {s.name}: target does not match keywords")
                    return False
            except Exception:
                raise
            name_u = (s.name or "").strip().upper()
            if name_u == "CRUEL BLADESMAN":
                try:
                    army = root.get_parent_army()
                except Exception:
                    raise
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is None or not getattr(mgr, "is_peerless_bladesmen", lambda: False)():
                    print(f"ERROR: {s.name}: wrong detachment")
                    return False
                try:
                    if not mgr.is_emperors_children_unit(root):
                        print(f"ERROR: {s.name}: target is not EMPEROR'S CHILDREN")
                        return False
                except Exception:
                    raise
            try:
                charged = bool(getattr(getattr(root, "round_state", None), "charged_this_round", False))
            except Exception:
                raise
            if spec.get("requires_charge") and not charged:
                print(f"ERROR: {s.name}: target did not charge this turn")
                return False
            try:
                fought = bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False))
            except Exception:
                raise
            if spec.get("requires_not_fought") and fought:
                print(f"ERROR: {s.name}: target already fought this phase")
                return False

            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                bonus = int(spec.get("ap_bonus", 1) or 1)
                sr["charge_melee_ap_bonus"] = int(sr.get("charge_melee_ap_bonus", 0) or 0) + bonus
                sr["charge_melee_ap_bonus_expires_phase"] = "FIGHT_PHASE"
                sr["charge_melee_ap_bonus_source"] = s.name
                root.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: {s.name}: {getattr(root, 'name', 'Unit')} gains +{int(spec.get('ap_bonus', 1) or 1)} AP on melee weapons this phase.")
            return True

        # Generic: extend Consolidation move distance with an engagement-range requirement (e.g., INCESSANT VIOLENCE).
        spec = self._get_consolidate_move_spec(s)
        if spec:
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                print(f"ERROR: {s.name}: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if "fight" not in str(phase_name or "").strip().lower():
                print(f"ERROR: {s.name}: wrong phase")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print(f"ERROR: {s.name}: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not self._unit_matches_defensive_target_spec(root, spec):
                    print(f"ERROR: {s.name}: target does not match keywords")
                    return False
            except Exception:
                raise
            if bool(spec.get("requires_engagement", False)):
                try:
                    max_dist = float(spec.get("max_distance", 0) or 0)
                except Exception:
                    max_dist = 0.0
                if max_dist > 0 and not self._consolidate_requires_engagement_possible(root, max_dist):
                    print(f"ERROR: {s.name}: no legal consolidation outcome")
                    return False
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                try:
                    max_dist = float(spec.get("max_distance", 0) or 0)
                except Exception:
                    raise
                if max_dist > 0:
                    try:
                        current = float(sr.get("stratagem_consolidate_distance_override", 0) or 0)
                    except Exception:
                        raise
                    if max_dist > current:
                        sr["stratagem_consolidate_distance_override"] = max_dist
                if bool(spec.get("requires_engagement", False)):
                    sr["stratagem_consolidate_requires_engagement"] = True
                sr["stratagem_consolidate_expires_phase"] = "FIGHT_PHASE"
                sr["stratagem_consolidate_source"] = s.name
                root.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: {s.name}: {getattr(root, 'name', 'Unit')} consolidates up to {int(spec.get('max_distance', 0) or 0)}\" this phase.")
            return True

        # Berzerker Warband: FRENZIED RESILIENCE (-1 Damage allocated this phase)
        if s.name.upper() == "FRENZIED RESILIENCE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            attacker_unit = kwargs.get("attacker_unit")
            candidates = kwargs.get("candidates") or kwargs.get("target_units") or []
            if unit is None:
                if candidates:
                    unit = candidates[0]
                else:
                    for r in reversed(self._pending_reactions):
                        if r.get("stratagem", "").strip().upper() == "FRENZIED RESILIENCE":
                            unit = r.get("unit") or r.get("target_unit")
                            attacker_unit = attacker_unit or r.get("attacking_unit")
                            candidates = candidates or (r.get("candidates") or [])
                            break
            if unit is None:
                print("WARN:O Frenzied Resilience: no target unit provided")
                return False
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_berzerker_warband", lambda: False)():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "fight phase":
                print("WARN:O Frenzied Resilience: wrong phase")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(unit):
                    print("WARN:O Frenzied Resilience: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not (hasattr(unit, "has_any_keyword") and unit.has_any_keyword("WORLD EATERS")):
                    print("WARN:O Frenzied Resilience: target is not WORLD EATERS")
                    return False
            except Exception:
                raise
            if candidates:
                try:
                    if unit not in list(candidates or []):
                        print("WARN:O Frenzied Resilience: target was not selected as a target")
                        return False
                except Exception:
                    raise
            if attacker_unit is not None:
                try:
                    if attacker_unit.get_parent_army().player is self.player:
                        print("WARN:O Frenzied Resilience: attacker is not enemy")
                        return False
                except Exception:
                    raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=unit).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["frenzied_resilience_active"] = True
                sr["frenzied_resilience_damage_reduction"] = 1
                sr["frenzied_resilience_expires_phase"] = "FIGHT_PHASE"
                unit.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: FRENZIED RESILIENCE: {getattr(unit, 'name', 'Unit')} reduces damage by 1 this phase.")
            return True

        # Berzerker Warband: SKULLS FOR THE SKULL THRONE! (extra unit-only Blessing of Khorne)
        if s.name.upper() == "SKULLS FOR THE SKULL THRONE!":
            unit = kwargs.get("unit") or kwargs.get("attacker_unit") or kwargs.get("target_unit")
            target_unit = kwargs.get("target_unit")
            blessings_ctx = kwargs.get("blessings_ctx") or kwargs.get("ctx") or kwargs.get("blessings_context")
            selected = kwargs.get("selected_blessings") or kwargs.get("selected_blessing_keys") or []
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "SKULLS FOR THE SKULL THRONE!":
                        unit = unit or r.get("unit") or r.get("attacker_unit")
                        target_unit = target_unit or r.get("target_unit")
                        blessings_ctx = blessings_ctx or r.get("blessings_ctx") or r.get("ctx")
                        selected = selected or r.get("selected_blessings") or r.get("selected_blessing_keys") or []
                        break
            if unit is None:
                print("WARN:O Skulls for the Skull Throne: no target unit provided")
                return False
            try:
                unit = unit.get_attached_unit_root()
            except Exception:
                raise
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_berzerker_warband", lambda: False)():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "fight phase":
                print("WARN:O Skulls for the Skull Throne: wrong phase")
                return False
            try:
                if _unit_cannot_be_target_of_stratagem(unit):
                    print("WARN:O Skulls for the Skull Throne: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not (hasattr(unit, "has_any_keyword") and unit.has_any_keyword("WORLD EATERS")):
                    print("WARN:O Skulls for the Skull Throne: target is not WORLD EATERS")
                    return False
            except Exception:
                raise
            if target_unit is not None:
                try:
                    is_char = bool(target_unit.has_keyword("Character"))
                    is_mon = bool(target_unit.has_keyword("Monster"))
                    if not (is_char or is_mon):
                        print("WARN:O Skulls for the Skull Throne: target was not CHARACTER or MONSTER")
                        return False
                except Exception:
                    raise
            if not selected:
                print("WARN:O Skulls for the Skull Throne: no blessing selected")
                return False
            mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
            if mgr is None:
                return False
            if blessings_ctx is not None:
                try:
                    preview = mgr.preview_choice(
                        blessings_ctx,
                        selected_blessing_keys=list(selected),
                        use_reborn_in_blood=False,
                    )
                except Exception:
                    raise
                if not preview.get("ok", False):
                    print("WARN:O Skulls for the Skull Throne: invalid blessing selection")
                    return False

            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=unit).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                br = int(getattr(self.game, "turn", 0) or 0)
            except Exception:
                raise
            if br <= 0:
                br = int(getattr(self.player, "round", 0) or 0)
            if not mgr.grant_unit_blessings(unit, blessing_keys=list(selected), battle_round=br):
                return False
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            try:
                chosen_names = []
                for k in list(selected):
                    kk = str(k).strip().upper()
                    d = mgr.definitions.get(kk)
                    chosen_names.append(d.name if d is not None else kk)
                print(f"INFO: SKULLS FOR THE SKULL THRONE!: {getattr(unit, 'name', 'Unit')} gains {', '.join(chosen_names)} until end of battle round.")
            except Exception:
                raise
            return True

        # Rage-cursed Onslaught: A GRIM WARNING (sticky objective on unit destruction)
        if s.name.upper() == "A GRIM WARNING":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            objective = kwargs.get("objective") or kwargs.get("objective_marker")
            candidates = kwargs.get("objective_candidates") or []
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "A GRIM WARNING":
                        unit = r.get("unit") or r.get("target_unit")
                        candidates = candidates or (r.get("objective_candidates") or [])
                        break
            if unit is None:
                print("ERROR: A Grim Warning: no target unit provided")
                return False
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if sm_mgr is None or not getattr(sm_mgr, "is_rage_cursed_onslaught", lambda: False)():
                return False
            try:
                if not unit.has_any_keyword("BLOOD ANGELS"):
                    return False
            except Exception:
                raise
            # Choose objective marker
            if objective is None:
                objective = candidates[0] if candidates else None
            if objective is None:
                print("ERROR: A Grim Warning: no objective marker available")
                return False
            if candidates:
                try:
                    if objective not in list(candidates or []):
                        print("ERROR: A Grim Warning: objective not in candidates")
                        return False
                except Exception:
                    raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=unit).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                loc = getattr(objective, "location", None)
                if loc is not None and hasattr(loc, "set_sticky_control"):
                    loc.set_sticky_control(self.player, source="a_grim_warning")
                elif loc is not None:
                    loc.sticky_controller = self.player
                    loc.sticky_source = "a_grim_warning"
                    loc.controlling_player = self.player
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print("INFO: A GRIM WARNING: objective remains under your control until broken.")
            return True

        # Berzerker Warband: BLOOD OFFERING (sticky objective on unit destruction)
        if s.name.upper() == "BLOOD OFFERING":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            objective = kwargs.get("objective") or kwargs.get("objective_marker")
            candidates = kwargs.get("objective_candidates") or []
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "BLOOD OFFERING":
                        unit = r.get("unit") or r.get("target_unit")
                        candidates = candidates or (r.get("objective_candidates") or [])
                        break
            if unit is None:
                print("ERROR: Blood Offering: no target unit provided")
                return False
            try:
                army = unit.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_berzerker_warband", lambda: False)():
                return False
            # Choose objective marker
            if objective is None:
                objective = candidates[0] if candidates else None
            if objective is None:
                print("ERROR: Blood Offering: no objective marker available")
                return False
            # Spend CP
            if not self.player.spend_command_points(s.cp_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                loc = getattr(objective, "location", None)
                if loc is not None and hasattr(loc, "set_sticky_control"):
                    loc.set_sticky_control(self.player, source="blood_offering")
                elif loc is not None:
                    loc.sticky_controller = self.player
                    loc.sticky_source = "blood_offering"
                    loc.controlling_player = self.player
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print("INFO: BLOOD OFFERING: objective remains under your control until broken.")
            return True

        # Khorne Daemonkin: MURDER-CALL (return unit to Strategic Reserves)
        if s.name.upper() == "MURDER-CALL":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == "MURDER-CALL":
                        unit = r.get("unit") or r.get("target_unit")
                        break
            if unit is None:
                print("ERROR: Murder-Call: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            try:
                if root.get_parent_army().player is not self.player:
                    print("ERROR: Murder-Call: target unit is not yours")
                    return False
            except Exception:
                raise
            try:
                army = root.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                return False
            try:
                if not we_mgr.unit_is_blood_legions(root):
                    print("ERROR: Murder-Call: target is not BLOOD LEGIONS")
                    return False
            except Exception:
                raise
            try:
                if not root.is_alive():
                    print("ERROR: Murder-Call: target is not alive")
                    return False
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    print("ERROR: Murder-Call: target is already in reserves")
                    return False
            except Exception:
                raise
            game_map = getattr(self.game, "map", None)
            if game_map is None:
                print("ERROR: Murder-Call: no map context")
                return False
            try:
                for enemy in list(game_map.get_enemy_units(root) or []):
                    if not getattr(enemy, "is_alive", lambda: True)():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    if game_map.is_within_engagement_range(root, enemy):
                        print("INFO: Murder-Call: target is within Engagement Range")
                        return False
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False

            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                raise
            for member in members:
                try:
                    if hasattr(member, "set_reserve_status"):
                        member.set_reserve_status("strategic_reserves")
                    else:
                        member.reserve_status = "strategic_reserves"
                except Exception:
                    raise
                mark_fn = getattr(member, "mark_entered_reserves_midgame", None)
                if callable(mark_fn):
                    mark_fn(game=self.game)
                try:
                    if bool(getattr(member, "is_aircraft", False)) and not bool(getattr(member, "hover_mode", False)):
                        member._aircraft_return_turn = int(getattr(self.game, "turn", 0) or 0) + 1
                except Exception:
                    raise
                try:
                    member.deployed = True
                    member.reserve_turn_deployed = None
                    member.arrived_from_reserves_this_turn = False
                except Exception:
                    raise
                try:
                    if game_map is not None and hasattr(game_map, "units") and member in game_map.units:
                        game_map.units.remove(member)
                except Exception:
                    raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: Murder-Call: {getattr(root, 'name', 'Unit')} placed into Strategic Reserves.")
            return True

        # Khorne Daemonkin: SUMMONED BY SLAUGHTER (set up Bloodletters from Reserves)
        if s.name.upper() == "SUMMONED BY SLAUGHTER":
            target_unit = kwargs.get("target_unit") or kwargs.get("unit")
            destroyed_base = kwargs.get("destroyed_model_base") or kwargs.get("destroyed_base")
            destroyed_model = kwargs.get("destroyed_model") or kwargs.get("model")
            destroyed_unit = kwargs.get("destroyed_unit") or kwargs.get("unit_destroyed")
            candidates = kwargs.get("candidates") or []

            if target_unit is None:
                if candidates:
                    target_unit = candidates[0]
                else:
                    for r in reversed(self._pending_reactions):
                        if r.get("stratagem", "").strip().upper() == "SUMMONED BY SLAUGHTER":
                            target_unit = r.get("target_unit") or r.get("unit")
                            destroyed_base = destroyed_base or r.get("destroyed_model_base")
                            destroyed_model = destroyed_model or r.get("destroyed_model")
                            destroyed_unit = destroyed_unit or r.get("destroyed_unit")
                            candidates = candidates or (r.get("candidates") or [])
                            if target_unit is None and candidates:
                                target_unit = candidates[0]
                            break
            if target_unit is None:
                print("ERROR: Summoned by Slaughter: no target unit provided")
                return False
            try:
                root = target_unit.get_attached_unit_root()
            except Exception:
                raise
            try:
                if root.get_parent_army().player is not self.player:
                    print("ERROR: Summoned by Slaughter: target unit is not yours")
                    return False
            except Exception:
                raise
            try:
                army = root.get_parent_army()
            except Exception:
                raise
            we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                return False
            if not self._is_bloodletters_unit(root):
                print("ERROR: Summoned by Slaughter: target is not BLOODLETTERS")
                return False
            try:
                if not root.is_in_reserves():
                    print("ERROR: Summoned by Slaughter: target is not in Reserves")
                    return False
            except Exception:
                raise
            try:
                br = int(getattr(self.game, "turn", 0) or 0)
            except Exception:
                raise
            if br and int(self._used_battle_round.get("SUMMONED BY SLAUGHTER", 0) or 0) == br:
                print("ERROR: Summoned by Slaughter: already used this battle round")
                return False

            # FAQ: units that started the battle in Reserves cannot deploy in battle round 1.
            try:
                if br < 2 and bool(getattr(root, "_started_in_reserves", False)):
                    print("ERROR: Summoned by Slaughter: unit started in Reserves and cannot arrive in battle round 1")
                    return False
            except Exception:
                raise
            if destroyed_base is None and destroyed_model is not None:
                try:
                    destroyed_base = copy.deepcopy(getattr(destroyed_model, "model_base", None))
                except Exception:
                    raise
            if destroyed_base is None and destroyed_unit is not None:
                try:
                    destroyed_base = copy.deepcopy(getattr(destroyed_unit, "_last_known_base", None))
                except Exception:
                    raise
            if destroyed_base is None:
                print("ERROR: Summoned by Slaughter: missing destroyed model position")
                return False

            manual = bool(kwargs.get("manual_placement") or kwargs.get("placement_complete"))
            game_map = getattr(self.game, "map", None)

            if not manual:
                print("ERROR:O Summoned by Slaughter requires manual placement")
                return False

            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False

            # Finalize reserves arrival state.
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                raise
            if game_map is not None:
                try:
                    if hasattr(game_map, "place_unit") and root not in getattr(game_map, "units", []):
                        if not game_map.place_unit(root):
                            print("ERROR: Summoned by Slaughter: placement failed on map")
                            return False
                except Exception:
                    raise
            for member in members:
                finalize = getattr(member, "_finalize_reserves_arrival", None)
                if callable(finalize):
                    finalize(int(getattr(self.game, "turn", 0) or 0), game_map)
                else:
                    try:
                        member.deployed = True
                        member.reserve_status = "deployed"
                        member.reserve_turn_deployed = int(getattr(self.game, "turn", 0) or 0)
                        member.arrived_from_reserves_this_turn = True
                    except Exception:
                        raise
            try:
                self._used_battle_round["SUMMONED BY SLAUGHTER"] = int(getattr(self.game, "turn", 0) or 0)
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: Summoned by Slaughter: {getattr(root, 'name', 'Unit')} set up from Reserves.")
            return True

        # Necrons: UNYIELDING FORMS (defensive -1 to wound if S > T).
        if s.name.upper() == "UNYIELDING FORMS":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            attacker_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
            candidates = kwargs.get("candidates") or kwargs.get("target_units") or []
            if unit is None:
                if candidates:
                    unit = candidates[0] if len(candidates) == 1 else None
                if unit is None:
                    for r in reversed(self._pending_reactions):
                        if r.get("stratagem", "").strip().upper() == "UNYIELDING FORMS":
                            unit = r.get("unit") or r.get("target_unit")
                            attacker_unit = attacker_unit or r.get("attacking_unit")
                            candidates = candidates or (r.get("candidates") or [])
                            if unit is None and candidates and len(candidates) == 1:
                                unit = candidates[0]
                            break
            if unit is None:
                print("ERROR: UNYIELDING FORMS: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if not self._is_starshatter_arsenal():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            pname = str(phase_name or "").strip().lower()
            if pname not in ("shooting phase", "fight phase"):
                print("ERROR: UNYIELDING FORMS: wrong phase")
                return False
            if pname == "shooting phase":
                active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
                if active_player is self.player:
                    print("ERROR: UNYIELDING FORMS: not opponent's Shooting phase")
                    return False
            if candidates:
                try:
                    if root not in list(candidates or []):
                        print("ERROR: UNYIELDING FORMS: target was not selected by the attacker")
                        return False
                except Exception:
                    raise
            try:
                if root.get_parent_army().player is not self.player:
                    print("ERROR: UNYIELDING FORMS: target unit is not yours")
                    return False
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: UNYIELDING FORMS: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.is_alive():
                    return False
            except Exception:
                raise
            try:
                if not getattr(root, "deployed", False):
                    return False
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    return False
            except Exception:
                raise
            mgr = self._get_necrons_mgr()
            if mgr is not None:
                try:
                    if not mgr.unit_is_necrons(root):
                        print("ERROR: UNYIELDING FORMS: target is not NECRONS")
                        return False
                    if mgr.unit_is_titanic(root):
                        print("ERROR: UNYIELDING FORMS: target is TITANIC")
                        return False
                    if not mgr.unit_is_vehicle_or_mounted(root):
                        print("ERROR: UNYIELDING FORMS: target is not VEHICLE or MOUNTED")
                        return False
                except Exception:
                    raise
            if attacker_unit is not None:
                try:
                    if attacker_unit.get_parent_army().player is self.player:
                        print("ERROR: UNYIELDING FORMS: attacker is not enemy")
                        return False
                except Exception:
                    raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                entry = {
                    "value": 1,
                    "attack_type": "any",
                    "expires_phase": "SHOOTING_PHASE" if pname == "shooting phase" else "FIGHT_PHASE",
                    "source": s.name,
                    "requires_strength_gt_toughness": True,
                }
                self._append_defensive_effect(root, "defensive_wound_mods", entry)
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: UNYIELDING FORMS: {getattr(root, 'name', 'Unit')} is harder to wound this phase.")
            return True

        # Necrons: MERCILESS RECLAMATION (+1 to wound vs targets near objectives).
        if s.name.upper() == "MERCILESS RECLAMATION":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            candidates = kwargs.get("candidates") or []
            if unit is None:
                if candidates:
                    unit = candidates[0] if len(candidates) == 1 else None
            if unit is None:
                print("ERROR: MERCILESS RECLAMATION: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if not self._is_starshatter_arsenal():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            pname = str(phase_name or "").strip().lower()
            if pname not in ("shooting phase", "fight phase"):
                print("ERROR: MERCILESS RECLAMATION: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is not self.player:
                print("ERROR: MERCILESS RECLAMATION: not your turn")
                return False
            try:
                if root.get_parent_army().player is not self.player:
                    print("ERROR: MERCILESS RECLAMATION: target unit is not yours")
                    return False
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: MERCILESS RECLAMATION: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.is_alive():
                    return False
            except Exception:
                raise
            try:
                if not getattr(root, "deployed", False):
                    return False
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    return False
            except Exception:
                raise
            mgr = self._get_necrons_mgr()
            if mgr is not None:
                try:
                    if not mgr.unit_is_necrons(root):
                        print("ERROR: MERCILESS RECLAMATION: target is not NECRONS")
                        return False
                    if mgr.unit_is_titanic(root):
                        print("ERROR: MERCILESS RECLAMATION: target is TITANIC")
                        return False
                except Exception:
                    raise
            try:
                if pname == "shooting phase" and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                    print("ERROR: MERCILESS RECLAMATION: target already shot")
                    return False
                if pname == "fight phase" and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                    print("ERROR: MERCILESS RECLAMATION: target already fought")
                    return False
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["merciless_reclamation_active"] = True
                sr["merciless_reclamation_expires_phase"] = "SHOOTING_PHASE" if pname == "shooting phase" else "FIGHT_PHASE"
                root.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: MERCILESS RECLAMATION: {getattr(root, 'name', 'Unit')} gains +1 to wound vs objectives this phase.")
            return True

        # Necrons: DIMENSIONAL TUNNEL (move through models/terrain this phase).
        if s.name.upper() == "DIMENSIONAL TUNNEL":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            candidates = kwargs.get("candidates") or []
            if unit is None:
                if candidates:
                    unit = candidates[0] if len(candidates) == 1 else None
            if unit is None:
                print("ERROR: DIMENSIONAL TUNNEL: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if not self._is_starshatter_arsenal():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "movement phase":
                print("ERROR: DIMENSIONAL TUNNEL: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is not self.player:
                print("ERROR: DIMENSIONAL TUNNEL: not your turn")
                return False
            try:
                if root.get_parent_army().player is not self.player:
                    print("ERROR: DIMENSIONAL TUNNEL: target unit is not yours")
                    return False
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: DIMENSIONAL TUNNEL: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.is_alive():
                    return False
            except Exception:
                raise
            try:
                if not getattr(root, "deployed", False):
                    return False
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    return False
            except Exception:
                raise
            mgr = self._get_necrons_mgr()
            if mgr is not None:
                try:
                    if not mgr.unit_is_necrons(root):
                        print("ERROR: DIMENSIONAL TUNNEL: target is not NECRONS")
                        return False
                    if mgr.unit_is_titanic(root):
                        print("ERROR: DIMENSIONAL TUNNEL: target is TITANIC")
                        return False
                    if not mgr.unit_is_vehicle_or_mounted(root):
                        print("ERROR: DIMENSIONAL TUNNEL: target is not VEHICLE or MOUNTED")
                        return False
                except Exception:
                    raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                move_types = {"move", "advance", "fall_back"}
                current = set(sr.get("bearer_unit_phase_move_types") or [])
                added = [t for t in move_types if t not in current]
                if added:
                    current.update(added)
                    sr["bearer_unit_phase_move_types"] = sorted(current)
                    sr["dimensional_tunnel_added_phase_move_types"] = added
                sr["dimensional_tunnel_active"] = True
                sr["dimensional_tunnel_expires_phase"] = "MOVEMENT_PHASE"
                root.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: DIMENSIONAL TUNNEL: {getattr(root, 'name', 'Unit')} can move through models/terrain this phase.")
            return True

        # Necrons: CHRONOSHIFT (Advance roll fixed at 6 for this phase).
        if s.name.upper() == "CHRONOSHIFT":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            candidates = kwargs.get("candidates") or []
            if unit is None:
                if candidates:
                    unit = candidates[0] if len(candidates) == 1 else None
            if unit is None:
                print("ERROR: CHRONOSHIFT: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if not self._is_starshatter_arsenal():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "movement phase":
                print("ERROR: CHRONOSHIFT: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is not self.player:
                print("ERROR: CHRONOSHIFT: not your turn")
                return False
            try:
                if root.get_parent_army().player is not self.player:
                    print("ERROR: CHRONOSHIFT: target unit is not yours")
                    return False
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: CHRONOSHIFT: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.is_alive():
                    return False
            except Exception:
                raise
            try:
                if not getattr(root, "deployed", False):
                    return False
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    return False
            except Exception:
                raise
            mgr = self._get_necrons_mgr()
            if mgr is not None:
                try:
                    if not mgr.unit_is_necrons(root):
                        print("ERROR: CHRONOSHIFT: target is not NECRONS")
                        return False
                    if mgr.unit_is_titanic(root):
                        print("ERROR: CHRONOSHIFT: target is TITANIC")
                        return False
                    if not mgr.unit_is_vehicle_or_mounted(root):
                        print("ERROR: CHRONOSHIFT: target is not VEHICLE or MOUNTED")
                        return False
                except Exception:
                    raise
            try:
                if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
                    print("ERROR: CHRONOSHIFT: target already moved this phase")
                    return False
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["chronoshift_active"] = True
                sr["chronoshift_expires_phase"] = "MOVEMENT_PHASE"
                root.special_rules = sr
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: CHRONOSHIFT: {getattr(root, 'name', 'Unit')} gains a fixed 6\" Advance this phase.")
            return True

        # Necrons: ENDLESS SERVITUDE (trigger Reanimation Protocols).
        if s.name.upper() == "ENDLESS SERVITUDE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            candidates = kwargs.get("candidates") or []
            if unit is None:
                if candidates:
                    unit = candidates[0] if len(candidates) == 1 else None
                if unit is None:
                    for r in reversed(self._pending_reactions):
                        if r.get("stratagem", "").strip().upper() == "ENDLESS SERVITUDE":
                            unit = r.get("unit") or r.get("target_unit")
                            candidates = candidates or (r.get("candidates") or [])
                            if unit is None and candidates and len(candidates) == 1:
                                unit = candidates[0]
                            break
            if unit is None:
                print("ERROR: ENDLESS SERVITUDE: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if not self._is_starshatter_arsenal():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "fight phase":
                print("ERROR: ENDLESS SERVITUDE: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is not self.player:
                print("ERROR: ENDLESS SERVITUDE: not your turn")
                return False
            try:
                if root.get_parent_army().player is not self.player:
                    print("ERROR: ENDLESS SERVITUDE: target unit is not yours")
                    return False
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: ENDLESS SERVITUDE: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.is_alive():
                    return False
            except Exception:
                raise
            try:
                if not getattr(root, "deployed", False):
                    return False
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    return False
            except Exception:
                raise
            mgr = self._get_necrons_mgr()
            if mgr is not None:
                try:
                    if not mgr.unit_is_necrons(root):
                        print("ERROR: ENDLESS SERVITUDE: target is not NECRONS")
                        return False
                    if mgr.unit_is_titanic(root):
                        print("ERROR: ENDLESS SERVITUDE: target is TITANIC")
                        return False
                except Exception:
                    raise
            try:
                has_rp = getattr(root, "attached_unit_has_reanimation_protocols", None)
                if callable(has_rp) and not has_rp():
                    print("ERROR: ENDLESS SERVITUDE: unit lacks Reanimation Protocols")
                    return False
            except Exception:
                raise
            game_map = getattr(self.game, "map", None)
            if game_map is None:
                print("ERROR: ENDLESS SERVITUDE: no map context")
                return False
            in_controlled = False
            for obj in list(getattr(game_map, "objectives", []) or []):
                loc = getattr(obj, "location", None)
                if loc is None or getattr(loc, "removed", False):
                    continue
                try:
                    if hasattr(loc, "update_control"):
                        loc.update_control(self.game)
                except Exception:
                    pass
                if getattr(loc, "controlling_player", None) is not self.player:
                    continue
                try:
                    if root.is_within_objective_range(loc):
                        in_controlled = True
                        break
                except Exception:
                    continue
            if not in_controlled:
                print("ERROR: ENDLESS SERVITUDE: unit is not within a controlled objective")
                return False
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                roll = int(dice_module.get_roll("D3") or 0)
            except Exception:
                raise
            if roll > 0:
                try:
                    provider = getattr(game_map, "reanimation_allocation_provider", None)
                    is_human = bool(getattr(self.player, "has_control", lambda: False)())
                    root.apply_reanimation_protocols(roll, game_map=game_map, is_human=is_human, provider=provider)
                except Exception:
                    raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: ENDLESS SERVITUDE: {getattr(root, 'name', 'Unit')} reanimates (rolled {int(roll or 0)}).")
            return True

        # Necrons: REACTIVE REPOSITION (reactive Normal move D6").
        if s.name.upper() == "REACTIVE REPOSITION":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacker_unit")
            candidates = kwargs.get("candidates") or []
            if unit is None:
                if candidates:
                    unit = candidates[0] if len(candidates) == 1 else None
                if unit is None:
                    for r in reversed(self._pending_reactions):
                        if r.get("stratagem", "").strip().upper() == "REACTIVE REPOSITION":
                            unit = r.get("unit") or r.get("target_unit")
                            enemy_unit = enemy_unit or r.get("enemy_unit")
                            candidates = candidates or (r.get("candidates") or [])
                            if unit is None and candidates and len(candidates) == 1:
                                unit = candidates[0]
                            break
            if unit is None:
                print("ERROR: REACTIVE REPOSITION: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if not self._is_starshatter_arsenal():
                return False
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            if str(phase_name or "").strip().lower() != "shooting phase":
                print("ERROR: REACTIVE REPOSITION: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game else None
            if active_player is self.player:
                print("ERROR: REACTIVE REPOSITION: not opponent's Shooting phase")
                return False
            if candidates:
                try:
                    if root not in list(candidates or []):
                        print("ERROR: REACTIVE REPOSITION: target was not selected by the attacker")
                        return False
                except Exception:
                    raise
            try:
                if root.get_parent_army().player is not self.player:
                    print("ERROR: REACTIVE REPOSITION: target unit is not yours")
                    return False
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print("ERROR: REACTIVE REPOSITION: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not root.is_alive():
                    return False
            except Exception:
                raise
            try:
                if not getattr(root, "deployed", False):
                    return False
            except Exception:
                raise
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    return False
            except Exception:
                raise
            mgr = self._get_necrons_mgr()
            if mgr is not None:
                try:
                    if not mgr.unit_is_necrons(root):
                        print("ERROR: REACTIVE REPOSITION: target is not NECRONS")
                        return False
                    if mgr.unit_is_titanic(root):
                        print("ERROR: REACTIVE REPOSITION: target is TITANIC")
                        return False
                except Exception:
                    raise
            if enemy_unit is not None:
                try:
                    if enemy_unit.get_parent_army().player is self.player:
                        print("ERROR: REACTIVE REPOSITION: attacker is not enemy")
                        return False
                except Exception:
                    raise
            game_map = getattr(self.game, "map", None)
            if game_map is None:
                print("ERROR: REACTIVE REPOSITION: no map context")
                return False
            try:
                engaged = False
                for enemy in list(game_map.get_enemy_units(root) or []):
                    if not getattr(enemy, "is_alive", lambda: True)():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    if game_map.is_within_engagement_range(root, enemy):
                        engaged = True
                        break
                if engaged:
                    print("ERROR: REACTIVE REPOSITION: unit is in Engagement Range")
                    return False
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            try:
                roll = int(dice_module.get_roll("D6") or 0)
            except Exception:
                raise
            move_max = max(0, int(roll or 0))
            req = None
            try:
                if self.game is not None:
                    req = self.game._queue_reactive_move_movement_decision(
                        player=self.player,
                        unit=root,
                        max_distance=int(move_max),
                        kind="reactive_reposition",
                        movement_type="reactive",
                        source=s.name,
                        attacker_unit=enemy_unit,
                    )
            except Exception:
                raise
            try:
                if req is not None and self.game is not None and hasattr(self.game, "event_system"):
                    self.game.event_system.publish(
                        "reactive_reposition_move",
                        player=self.player,
                        unit=root,
                        max_distance=int(move_max),
                        decision_request=req,
                    )
            except Exception:
                raise
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            print(f"INFO: REACTIVE REPOSITION: {getattr(root, 'name', 'Unit')} can move {int(move_max)}\".")
            return True

        # Generic defensive reaction stratagems (after targets selected).
        spec = self._get_defensive_reaction_spec(s)
        if spec:
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            attacker_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
            candidates = kwargs.get("candidates") or kwargs.get("target_units") or []
            if unit is None:
                for r in reversed(self._pending_reactions):
                    if r.get("stratagem", "").strip().upper() == (s.name or "").strip().upper():
                        unit = unit or r.get("unit") or r.get("target_unit")
                        attacker_unit = attacker_unit or r.get("attacking_unit")
                        if not candidates:
                            candidates = r.get("candidates") or r.get("target_units") or []
                        break
            if unit is None:
                print(f"ERROR: {s.name}: no target unit provided")
                return False
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                raise
            if root is None:
                return False
            if candidates:
                try:
                    if root not in list(candidates or []):
                        print(f"ERROR: {s.name}: target was not selected by the attacker")
                        return False
                except Exception:
                    raise
            phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
            phase_key = str(phase_name or "").strip().lower()
            phase_tag = "shooting" if "shooting" in phase_key else "fight" if "fight" in phase_key else None
            if phase_tag is None or phase_tag not in set(spec.get("phases") or []):
                print(f"ERROR: {s.name}: wrong phase")
                return False
            if spec.get("duration") == "attacker" and attacker_unit is None:
                print(f"ERROR: {s.name}: missing attacker context")
                return False
            try:
                if attacker_unit is not None and attacker_unit.get_parent_army().player is self.player:
                    print(f"ERROR: {s.name}: attacker is not enemy")
                    return False
            except Exception:
                raise
            try:
                if _unit_cannot_be_target_of_stratagem(root):
                    print(f"ERROR: {s.name}: target cannot be selected")
                    return False
            except Exception:
                raise
            try:
                if not self._unit_matches_defensive_target_spec(root, spec):
                    print(f"ERROR: {s.name}: target does not match keywords")
                    return False
            except Exception:
                raise
            eff_cost = s.cp_cost
            try:
                if hasattr(self.player, "apply_stratagem_cp_cost"):
                    eff_cost = int(self.player.apply_stratagem_cp_cost(s, target_unit=root).get("cost", s.cp_cost))
            except Exception:
                raise
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            if not self._apply_generic_defensive_effect(
                root,
                spec,
                attacker_unit=attacker_unit,
                phase_name=phase_name or "",
                source_name=s.name,
            ):
                return False
            if kwargs.get("dequeue") is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
            try:
                print(f"WARN: {s.name}: {defensive_reaction_note(spec)}")
            except Exception:
                raise
            return True

        # Provide phase_name for timing checks
        if 'phase_name' not in kwargs:
            kwargs['phase_name'] = self._current_phase_name
        ok = s.use(self.player, self.game, **kwargs)
        if ok:
            # Mark per-turn limiter
            key = s.name.upper()
            if key in self._used_this_turn:
                self._used_this_turn[key] = True
            # If this was a queued reaction, drop it
            if 'dequeue' in kwargs and kwargs['dequeue'] is True:
                self._dequeue_reaction_by_name(s.name)
            try:
                self._used_stratagems_this_phase.add((s.name or "").strip().upper())
            except Exception:
                raise
        return ok

    # -------- UI helpers for non-disruptive prompts --------
    def get_phase_stratagem_items(self) -> List[Dict[str, Any]]:
        self._prune_expired_reactions()
        phase_name = self._current_phase_name or ""
        active_player = self.game.get_current_player() if self.game else None
        is_active_turn = active_player is self.player
        now = self._now()

        items: List[Dict[str, Any]] = []
        pending_names: set[str] = set()

        # Pending reactions first
        for r in list(self._pending_reactions):
            s = self.get_by_name(str(r.get("stratagem", "")))
            if not s or not self._is_implemented_stratagem(s):
                continue
            ctx = dict(r)
            if "phase_name" not in ctx and phase_name:
                ctx["phase_name"] = phase_name
            try:
                reaction_phase = ctx.get("phase_name") or ctx.get("phase")
            except Exception:
                raise
            if reaction_phase and phase_name:
                if str(reaction_phase).strip().lower() != str(phase_name).strip().lower():
                    continue
            if not s.is_phase_allowed(ctx.get("phase_name", "") or phase_name):
                continue
            availability = self._evaluate_availability(s, ctx, is_active_turn=is_active_turn)
            time_left = None
            if availability["available"]:
                time_left = self._reaction_time_left(r, now=now)
            trigger_label = ""
            try:
                if r.get("event") == "enemy_move":
                    action = str(r.get("action", "") or "").strip().lower()
                    when = str(r.get("when", "") or "").strip().lower()
                    if action == "charge":
                        trigger_label = "Trigger: enemy charge"
                    elif when == "start":
                        trigger_label = "Trigger: enemy move start"
                    elif when == "end":
                        trigger_label = "Trigger: enemy move end"
                elif r.get("event") in ("charge_move_ended", "heroic_intervention"):
                    trigger_label = "Trigger: enemy charge end"
                elif r.get("event") == "shooting_targets_selected":
                    trigger_label = "Trigger: after targets selected"
                elif r.get("event") == "blood_surge_triggered":
                    trigger_label = "Trigger: after enemy shooting"
                elif r.get("event") == "fight_sequence_complete":
                    trigger_label = "Trigger: after enemy fought"
                elif r.get("event") == "before_consolidate":
                    trigger_label = "Trigger: before consolidate"
                elif r.get("event") == "roll_made":
                    trigger_label = "Trigger: roll made"
                elif r.get("event") == "battle_shock_test_started":
                    trigger_label = "Trigger: battle-shock test"
                elif r.get("event") == "phase_end":
                    trigger_label = "Trigger: phase end"
            except Exception:
                raise
            items.append({
                "name": s.name,
                "cp_cost": availability["cp_cost"],
                "available": availability["available"],
                "reason": availability["reason"],
                "turn_category": self._turn_category(s),
                "is_reaction": True,
                "context": ctx,
                "target_label": self._reaction_target_label(r),
                "trigger_label": trigger_label,
                "time_left": time_left,
            })
            try:
                pending_names.add((s.name or "").strip().upper())
            except Exception:
                raise
        # Phase-available stratagems (implemented only)
        for s in self.available:
            if not self._is_implemented_stratagem(s):
                continue
            if not s.is_phase_allowed(phase_name or ""):
                continue
            name_u = (s.name or "").strip().upper()
            is_reaction_only = (
                name_u in REACTION_ONLY_STRATAGEM_NAMES
                or self._get_defensive_reaction_spec(s) is not None
                or self._get_consolidate_move_spec(s) is not None
            )
            if name_u in pending_names and is_reaction_only:
                continue
            ctx = {"phase_name": phase_name}
            availability = self._evaluate_availability(s, ctx, is_active_turn=is_active_turn)
            if is_reaction_only:
                if availability["available"]:
                    availability["available"] = False
                    availability["reason"] = "No trigger"
                elif availability["reason"] in (None, "", "Requires valid trigger or target"):
                    availability["reason"] = "No trigger"
            target_hint = self._stratagem_target_hint(s.name)
            items.append({
                "name": s.name,
                "cp_cost": availability["cp_cost"],
                "available": availability["available"],
                "reason": availability["reason"],
                "turn_category": self._turn_category(s),
                "is_reaction": False,
                "context": ctx,
                "target_label": target_hint,
                "trigger_label": "",
                "time_left": None,
            })

        return items

    def get_pending_reactions(self, clear: bool = False) -> List[Dict[str, Any]]:
        self._prune_expired_reactions()
        items = list(self._pending_reactions)
        if clear:
            self._pending_reactions = []
        return items
