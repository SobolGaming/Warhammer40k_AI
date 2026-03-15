from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Tuple


@dataclass(frozen=True)
class AttackRollCondition:
    attacker_below_starting_strength: bool = False
    attacker_below_half_strength: bool = False
    attacker_charged_this_turn: bool = False
    attacker_charge_related_this_turn: bool = False
    attacker_waaagh_active: bool = False
    attacker_contains_model_keywords_any: Tuple[str, ...] = ()
    attacker_within_objective_controlled: bool = False
    target_below_starting_strength: bool = False
    target_battleshocked: bool = False
    target_within_objective: bool = False
    target_within_objective_not_controlled: bool = False
    target_within_range: Optional[float] = None
    target_isolated_within: Optional[float] = None
    target_keywords_any: Tuple[str, ...] = ()
    target_keywords_all: Tuple[str, ...] = ()
    target_exclude_keywords_any: Tuple[str, ...] = ()
    target_can_fly: Optional[bool] = None
    target_below_half_strength: bool = False

    def merge(self, other: "AttackRollCondition") -> "AttackRollCondition":
        if other is None:
            return self
        merged_range = self.target_within_range
        if other.target_within_range is not None:
            merged_range = other.target_within_range if merged_range is None else max(merged_range, other.target_within_range)
        merged_isolated = self.target_isolated_within
        if other.target_isolated_within is not None:
            merged_isolated = (
                other.target_isolated_within if merged_isolated is None else max(merged_isolated, other.target_isolated_within)
            )
        return AttackRollCondition(
            attacker_below_starting_strength=bool(
                self.attacker_below_starting_strength or other.attacker_below_starting_strength
            ),
            attacker_below_half_strength=bool(
                self.attacker_below_half_strength or other.attacker_below_half_strength
            ),
            attacker_charged_this_turn=bool(
                self.attacker_charged_this_turn or other.attacker_charged_this_turn
            ),
            attacker_charge_related_this_turn=bool(
                self.attacker_charge_related_this_turn or other.attacker_charge_related_this_turn
            ),
            attacker_waaagh_active=bool(
                self.attacker_waaagh_active or other.attacker_waaagh_active
            ),
            attacker_contains_model_keywords_any=tuple(
                {*(self.attacker_contains_model_keywords_any or ()), *(other.attacker_contains_model_keywords_any or ())}
            ),
            attacker_within_objective_controlled=bool(
                self.attacker_within_objective_controlled or other.attacker_within_objective_controlled
            ),
            target_below_starting_strength=bool(
                self.target_below_starting_strength or other.target_below_starting_strength
            ),
            target_battleshocked=bool(self.target_battleshocked or other.target_battleshocked),
            target_within_objective=bool(self.target_within_objective or other.target_within_objective),
            target_within_objective_not_controlled=bool(
                self.target_within_objective_not_controlled or other.target_within_objective_not_controlled
            ),
            target_within_range=merged_range,
            target_isolated_within=merged_isolated,
            target_keywords_any=tuple({*self.target_keywords_any, *other.target_keywords_any}),
            target_keywords_all=tuple({*self.target_keywords_all, *other.target_keywords_all}),
            target_exclude_keywords_any=tuple({*self.target_exclude_keywords_any, *other.target_exclude_keywords_any}),
            target_can_fly=other.target_can_fly if other.target_can_fly is not None else self.target_can_fly,
            target_below_half_strength=bool(self.target_below_half_strength or other.target_below_half_strength),
        )


@dataclass(frozen=True)
class AttackRollEffect:
    roll: str  # "hit" | "wound" | "damage"
    kind: str  # "add" | "sub" | "reroll" | "crit"
    value: int = 0
    reroll_values: Tuple[int, ...] = ()
    reroll_full: bool = False
    critical_threshold: Optional[int] = None
    condition: Optional[AttackRollCondition] = None


@dataclass(frozen=True)
class AttackRollRule:
    scope: str  # "leading" | "unit" | "model" | "aura" | "defensive"
    subject: str  # "model_in_this_unit" | "model_in_that_unit" | "this_model" | "attack_targets_unit"
    attack_type: str  # "melee" | "ranged" | "any"
    effects: Tuple[AttackRollEffect, ...]
    trigger_condition: Optional[AttackRollCondition] = None
    aura_range: Optional[float] = None
    aura_faction: Optional[str] = None
    aura_friendly: Optional[bool] = None


_HTML_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[a-z0-9]+")

_LEADING_PREFIX_RE = re.compile(
    r"^while (?P<who>.+?) is leading (?:a|this) unit[,;:]?\s*",
    flags=re.IGNORECASE,
)
_AURA_PREFIX_RE = re.compile(
    r'^while a (?P<aff>friendly|enemy) (?P<faction>.+?) unit is within (?P<rng>\d+)" of this (?:unit|model)[,;:]?\s*',
    flags=re.IGNORECASE,
)

_TRIGGER_ATTACK_RE = re.compile(
    r"^each time (?P<subject>this model|a model in (?:this|that) unit) makes (?:a|an)?\s*(?P<atype>melee|ranged)?\s*attack(?:s)?",
    flags=re.IGNORECASE,
)
_TRIGGER_TARGET_RE = re.compile(
    r"^each time (?:a|an)?\s*(?P<atype>melee|ranged)?\s*attack(?:s)? targets (?:this|that) (?P<target>unit|model)",
    flags=re.IGNORECASE,
)
_TRIGGER_TARGET_WITH_ATTACK_RE = re.compile(
    r"^each time (?P<subject>this model|a model in (?:this|that) unit) targets (?:an?|the)?\s*(?:enemy\s+)?"
    r"(?P<target>unit|model) with (?:a|an)?\s*(?P<atype>melee|ranged)?\s*attack(?:s)?",
    flags=re.IGNORECASE,
)

_EFFECT_START_RE = re.compile(
    r"^(?:if\b|add\b|subtract\b|improve\b|(?:you can )?reroll\b|a successful\b|an unmodified\b|a critical\b)",
    flags=re.IGNORECASE,
)
_EFFECT_PREAMBLE_RE = re.compile(r"^until (?:the )?end of the phase[,;:]?\s*", flags=re.IGNORECASE)


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    t = _HTML_RE.sub(" ", str(text))
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    t = re.sub(r"\ba model in the bearer'?s unit\b", "a model in this unit", t, flags=re.IGNORECASE)
    t = re.sub(r"\bmodels in the bearer'?s unit\b", "models in this unit", t, flags=re.IGNORECASE)
    t = re.sub(r"\bmonster\s+of\s+vehicle\b", "monster or vehicle", t, flags=re.IGNORECASE)
    t = re.sub(r"\bvehicle\s+of\s+monster\b", "vehicle or monster", t, flags=re.IGNORECASE)
    t = t.replace("unmodifed", "unmodified")
    t = t.replace("re-roll", "reroll")
    t = t.replace("\n", " ").replace("\r", " ")
    t = _SPACE_RE.sub(" ", t).strip()
    return t.lower()


def _strip_punct(text: str) -> str:
    return re.sub(r"[.,;:]+$", "", text).strip()


def _has_tokens(text: str) -> bool:
    return bool(_WORD_RE.search(text or ""))


def _strip_effect_preamble(text: str) -> str:
    t = text.strip()
    while True:
        m = _EFFECT_PREAMBLE_RE.match(t)
        if not m:
            break
        t = t[m.end():].lstrip(" ,;:")
    return t


def _split_effect_clauses(text: str) -> Optional[list[str]]:
    parts: list[str] = []
    for segment in re.split(r"[.;]+", text):
        s = segment.strip()
        if not s:
            continue
        while s:
            s = s.lstrip(" ,;:")
            if not s:
                break
            s = _strip_effect_preamble(s)
            if not s:
                break
            if not _EFFECT_START_RE.match(s):
                return None
            next_idx = None
            for m in re.finditer(r"\band\b", s):
                rest = s[m.end():].lstrip(" ,;:")
                rest = _strip_effect_preamble(rest)
                if _EFFECT_START_RE.match(rest):
                    next_idx = m.start()
                    break
            if next_idx is None:
                parts.append(s.strip(" ,"))
                break
            parts.append(s[:next_idx].strip(" ,"))
            s = s[next_idx + len("and"):].strip()
    return parts


def _parse_condition(text: str) -> Optional[AttackRollCondition]:
    t = _strip_punct(text.strip())
    if not t:
        return None

    if re.fullmatch(r"(?:the )?target (?:of that attack )?is battle-?shocked", t):
        return AttackRollCondition(target_battleshocked=True)
    if re.fullmatch(r"that target is battle-?shocked", t):
        return AttackRollCondition(target_battleshocked=True)
    if re.fullmatch(r"that enemy unit is battle-?shocked", t):
        return AttackRollCondition(target_battleshocked=True)

    if re.fullmatch(r"(?:this model|this unit|it) is (?:also )?below (?:its )?starting strength", t):
        return AttackRollCondition(attacker_below_starting_strength=True)
    if re.fullmatch(r"(?:this model|this unit|it) is (?:also )?below half[- ]strength", t):
        return AttackRollCondition(attacker_below_half_strength=True)

    if re.fullmatch(r"(?:this model|this unit|it|that unit) made a charge move this turn", t):
        return AttackRollCondition(attacker_charged_this_turn=True)
    if re.fullmatch(
        r"(?:this model|this unit|it|that unit) made a charge move or was charged this turn",
        t,
    ):
        return AttackRollCondition(attacker_charge_related_this_turn=True)
    if re.fullmatch(
        r"(?:this model|this unit|it|that unit) was charged this turn",
        t,
    ):
        return AttackRollCondition(attacker_charge_related_this_turn=True)
    if re.fullmatch(r"the waaagh!? is active for your army", t):
        return AttackRollCondition(attacker_waaagh_active=True)

    m = re.fullmatch(
        r"(?:this unit|that unit|it) contains (?:an?|one or more)?\s*(?P<model>[a-z0-9 \\-]+?)(?: models?)?",
        t,
    )
    if m:
        model_kw = str(m.group("model") or "").strip()
        if model_kw:
            return AttackRollCondition(attacker_contains_model_keywords_any=(model_kw,))

    if re.fullmatch(
        r"(?:this model|this unit|it|that unit) is within range of (?:an|one or more) objective marker(?:s)? you control",
        t,
    ):
        return AttackRollCondition(attacker_within_objective_controlled=True)

    if re.fullmatch(r"that unit is (?:also )?below (?:its )?starting strength", t):
        return AttackRollCondition(attacker_below_starting_strength=True)
    if re.fullmatch(r"that unit is (?:also )?below half[- ]strength", t):
        return AttackRollCondition(attacker_below_half_strength=True)
    if re.fullmatch(r"that enemy unit is (?:also )?below (?:its )?starting strength", t):
        return AttackRollCondition(target_below_starting_strength=True)
    if re.fullmatch(r"that enemy unit is (?:also )?below half[- ]strength", t):
        return AttackRollCondition(target_below_half_strength=True)
    if re.fullmatch(r"that target is (?:also )?below (?:its )?starting strength", t):
        return AttackRollCondition(target_below_starting_strength=True)
    if re.fullmatch(r"that target is (?:also )?below half[- ]strength", t):
        return AttackRollCondition(target_below_half_strength=True)
    if re.fullmatch(r"that (?:enemy )?unit is afflicted", t):
        return AttackRollCondition(target_keywords_any=("afflicted",))

    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*unit within range of (?:an|one or more) objective marker(?:s)?",
        t,
    ):
        return AttackRollCondition(target_within_objective=True)
    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*unit within range of (?:an|one or more) objective marker(?:s)? you do not control",
        t,
    ):
        return AttackRollCondition(target_within_objective_not_controlled=True)
    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*unit that is within range of (?:an|one or more) objective marker(?:s)?",
        t,
    ):
        return AttackRollCondition(target_within_objective=True)
    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*unit that is within range of (?:an|one or more) objective marker(?:s)? you do not control",
        t,
    ):
        return AttackRollCondition(target_within_objective_not_controlled=True)
    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*enemy unit within range of (?:an|one or more) objective marker(?:s)?",
        t,
    ):
        return AttackRollCondition(target_within_objective=True)
    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*enemy unit within range of (?:an|one or more) objective marker(?:s)? you do not control",
        t,
    ):
        return AttackRollCondition(target_within_objective_not_controlled=True)
    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*enemy unit that is within range of (?:an|one or more) objective marker(?:s)?",
        t,
    ):
        return AttackRollCondition(target_within_objective=True)
    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*enemy unit that is within range of (?:an|one or more) objective marker(?:s)? you do not control",
        t,
    ):
        return AttackRollCondition(target_within_objective_not_controlled=True)

    if re.fullmatch(r"that (?:enemy )?unit is within range of (?:an|one or more) objective marker(?:s)?", t):
        return AttackRollCondition(target_within_objective=True)
    if re.fullmatch(r"that (?:enemy )?unit is within range of (?:an|one or more) objective marker(?:s)? you do not control", t):
        return AttackRollCondition(target_within_objective_not_controlled=True)
    if re.fullmatch(r"(?:the )?target is within range of (?:an|one or more) objective marker(?:s)?", t):
        return AttackRollCondition(target_within_objective=True)
    if re.fullmatch(r"(?:the )?target is within range of (?:an|one or more) objective marker(?:s)? you do not control", t):
        return AttackRollCondition(target_within_objective_not_controlled=True)
    if re.fullmatch(
        r"(?:the )?target(?: of that attack)? is within range of (?:an|one or more) objective marker(?:s)?",
        t,
    ):
        return AttackRollCondition(target_within_objective=True)
    if re.fullmatch(
        r"(?:the )?target(?: of that attack)? is within range of (?:an|one or more) objective marker(?:s)? "
        r"(?:you do not control|your opponent controls)",
        t,
    ):
        return AttackRollCondition(target_within_objective_not_controlled=True)
    if re.fullmatch(
        r"(?:the )?target(?: of that attack)? is (?:an?|the)?\s*(?:enemy\s+)?unit(?: that is)? within range of (?:an|one or more) objective marker(?:s)?",
        t,
    ):
        return AttackRollCondition(target_within_objective=True)
    if re.fullmatch(
        r"(?:the )?target(?: of that attack)? is (?:an?|the)?\s*(?:enemy\s+)?unit(?: that is)? within range of "
        r"(?:an|one or more) objective marker(?:s)? (?:you do not control|your opponent controls)",
        t,
    ):
        return AttackRollCondition(target_within_objective_not_controlled=True)

    m = re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*unit within (?P<rng>\d+)\"",
        t,
    )
    if m:
        return AttackRollCondition(target_within_range=float(m.group("rng")))
    m = re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*unit that is within (?P<rng>\d+)\"",
        t,
    )
    if m:
        return AttackRollCondition(target_within_range=float(m.group("rng")))
    m = re.fullmatch(r"that (?:enemy )?unit is within (?P<rng>\d+)\"", t)
    if m:
        return AttackRollCondition(target_within_range=float(m.group("rng")))

    m = re.fullmatch(
        r"there are no other (?:enemy )?units?(?: from your opponent's army)?(?: are)? within (?P<rng>\d+)\" of (?:that|the) target",
        t,
    )
    if m:
        return AttackRollCondition(target_isolated_within=float(m.group("rng")))

    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*unit that can fly",
        t,
    ):
        return AttackRollCondition(target_can_fly=True)
    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*unit that cannot fly",
        t,
    ):
        return AttackRollCondition(target_can_fly=False)

    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*character (?:unit|model)",
        t,
    ):
        return AttackRollCondition(target_keywords_any=("character",))
    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*monster or vehicle unit",
        t,
    ):
        return AttackRollCondition(target_keywords_any=("monster", "vehicle"))

    m = re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*(?:enemy\s+)?unit that is below (?:its )?starting strength",
        t,
    )
    if m:
        return AttackRollCondition(target_below_starting_strength=True)
    m = re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*(?:enemy\s+)?unit that is below half[- ]strength",
        t,
    )
    if m:
        return AttackRollCondition(target_below_half_strength=True)

    m = re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*unit \(excluding (?P<ex>[^)]+)\)",
        t,
    )
    if m:
        raw = m.group("ex").replace(" and ", ",")
        parts = tuple(p.strip().lower() for p in raw.split(",") if p.strip())
        if parts:
            return AttackRollCondition(target_exclude_keywords_any=parts)

    m = re.fullmatch(r"(?:the target of that attack|that attack) targets (?P<clause>.+)", t)
    if m:
        return _parse_target_clause(m.group("clause"))

    return None


def _parse_target_clause(text: str) -> Optional[AttackRollCondition]:
    t = _strip_punct(text.strip())
    if not t:
        return None
    if t.startswith("a "):
        t = t[2:]
    if t.startswith("an "):
        t = t[3:]
    if t.startswith("enemy "):
        t = t[6:]

    if t in ("unit", "model"):
        return AttackRollCondition()

    if re.fullmatch(r"unit that can fly", t):
        return AttackRollCondition(target_can_fly=True)
    if re.fullmatch(r"unit that cannot fly", t):
        return AttackRollCondition(target_can_fly=False)
    if re.fullmatch(r"(?:an? )?afflicted unit", t):
        return AttackRollCondition(target_keywords_any=("afflicted",))
    if re.fullmatch(r"unit that is afflicted", t):
        return AttackRollCondition(target_keywords_any=("afflicted",))
    if re.fullmatch(r"battle-?shocked unit", t):
        return AttackRollCondition(target_battleshocked=True)
    if re.fullmatch(r"unit that is battle-?shocked", t):
        return AttackRollCondition(target_battleshocked=True)
    if re.fullmatch(r"character (?:unit|model)", t):
        return AttackRollCondition(target_keywords_any=("character",))
    if re.fullmatch(r"monster or vehicle unit", t):
        return AttackRollCondition(target_keywords_any=("monster", "vehicle"))
    if re.fullmatch(r"unit within range of (?:an|one or more) objective marker(?:s)?", t):
        return AttackRollCondition(target_within_objective=True)
    if re.fullmatch(r"unit that is within range of (?:an|one or more) objective marker(?:s)?", t):
        return AttackRollCondition(target_within_objective=True)
    m = re.fullmatch(r"unit within (?P<rng>\d+)\"", t)
    if m:
        return AttackRollCondition(target_within_range=float(m.group("rng")))
    m = re.fullmatch(r"unit that is within (?P<rng>\d+)\"", t)
    if m:
        return AttackRollCondition(target_within_range=float(m.group("rng")))
    m = re.fullmatch(r"unit that is below (?:its )?starting strength", t)
    if m:
        return AttackRollCondition(target_below_starting_strength=True)
    m = re.fullmatch(r"unit that is below half[- ]strength", t)
    if m:
        return AttackRollCondition(target_below_half_strength=True)
    m = re.fullmatch(r"unit below (?:its )?starting strength", t)
    if m:
        return AttackRollCondition(target_below_starting_strength=True)
    m = re.fullmatch(r"unit below half[- ]strength", t)
    if m:
        return AttackRollCondition(target_below_half_strength=True)
    m = re.fullmatch(r"unit \(excluding (?P<ex>[^)]+)\)", t)
    if m:
        raw = m.group("ex").replace(" and ", ",")
        parts = tuple(p.strip().lower() for p in raw.split(",") if p.strip())
        if parts:
            return AttackRollCondition(target_exclude_keywords_any=parts)
    keywords = _parse_keyword_list_clause(t)
    if keywords:
        return AttackRollCondition(target_keywords_any=keywords)
    return None


def _parse_keyword_list_clause(text: str) -> Optional[Tuple[str, ...]]:
    t = _strip_punct(text.strip())
    if not t:
        return None
    for prefix in ("a ", "an ", "enemy "):
        if t.startswith(prefix):
            t = t[len(prefix):].strip()
    t = re.sub(r"\b(units?|models?)$", "", t).strip()
    if not t:
        return None
    if not any(sep in t for sep in (" or ", ",", " and ")):
        return None
    for blocked in ("within ", "objective", "below", "battle", "can fly", "cannot fly", "that is", "that are", "excluding"):
        if blocked in t:
            return None
    keywords: list[str] = []
    for chunk in t.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if " or " in chunk:
            parts = [p.strip() for p in chunk.split(" or ") if p.strip()]
        elif " and " in chunk:
            parts = [p.strip() for p in chunk.split(" and ") if p.strip()]
        else:
            parts = [chunk]
        for part in parts:
            if not part:
                continue
            if part in ("unit", "model"):
                continue
            if part not in keywords:
                keywords.append(part)
    if not keywords:
        return None
    return tuple(keywords)


def _parse_effect_clause(text: str) -> Optional[AttackRollEffect]:
    clause = _strip_punct(text.strip())
    if not clause:
        return None

    condition = None
    if clause.startswith("if "):
        if "," not in clause:
            return None
        cond_text, clause = clause.split(",", 1)
        condition = _parse_condition(cond_text[3:].strip())
        if condition is None:
            return None
        clause = _strip_punct(clause.strip())
    else:
        if " if " in clause:
            effect_text, cond_text = clause.split(" if ", 1)
            cond = _parse_condition(cond_text.strip())
            if cond is None:
                return None
            condition = cond
            clause = _strip_punct(effect_text.strip())

    clause = clause.replace(" as well", "").strip()
    clause = _strip_effect_preamble(clause)

    m = re.fullmatch(r"add (?P<val>\d+) to the (?P<roll>hit|wound) roll", clause)
    if m:
        return AttackRollEffect(
            roll=m.group("roll"),
            kind="add",
            value=int(m.group("val")),
            condition=condition,
        )
    m = re.fullmatch(r"subtract (?P<val>\d+) from the (?P<roll>hit|wound) roll", clause)
    if m:
        return AttackRollEffect(
            roll=m.group("roll"),
            kind="sub",
            value=int(m.group("val")),
            condition=condition,
        )

    m = re.fullmatch(r"add (?P<val>\d+) to the damage characteristic of that attack", clause)
    if m:
        return AttackRollEffect(
            roll="damage",
            kind="add",
            value=int(m.group("val")),
            condition=condition,
        )
    m = re.fullmatch(r"improve the damage characteristic of that attack by (?P<val>\d+)", clause)
    if m:
        return AttackRollEffect(
            roll="damage",
            kind="add",
            value=int(m.group("val")),
            condition=condition,
        )
    m = re.fullmatch(r"subtract (?P<val>\d+) from the damage characteristic of that attack", clause)
    if m:
        return AttackRollEffect(
            roll="damage",
            kind="sub",
            value=int(m.group("val")),
            condition=condition,
        )

    m = re.fullmatch(
        r"(?:you can )?reroll (?:a|any|the)?\s*(?P<roll>hit|wound) roll(?:s)?(?: of (?P<val>\d))?(?P<instead> instead)?",
        clause,
    )
    if m:
        reroll_full = m.group("val") is None or bool(m.group("instead"))
        reroll_values: tuple[int, ...] = ()
        if m.group("val") is not None:
            reroll_values = (int(m.group("val")),)
        return AttackRollEffect(
            roll=m.group("roll"),
            kind="reroll",
            reroll_values=reroll_values,
            reroll_full=bool(reroll_full),
            condition=condition,
        )

    m = re.fullmatch(
        r"(?:a successful|an) unmodified (?P<roll>hit|wound) roll of (?P<thresh>\d)\+ scores a critical (?P<ctype>hit|wound)"
        r"(?:,? instead of only a 6)?",
        clause,
    )
    if m:
        return AttackRollEffect(
            roll=m.group("roll"),
            kind="crit",
            critical_threshold=int(m.group("thresh")),
            condition=condition,
        )
    m = re.fullmatch(
        r"a critical (?P<ctype>hit|wound) is scored on an unmodified (?P<roll>hit|wound) roll of (?P<thresh>\d)\+"
        r"(?:,? instead of only a 6)?",
        clause,
    )
    if m:
        return AttackRollEffect(
            roll=m.group("roll"),
            kind="crit",
            critical_threshold=int(m.group("thresh")),
            condition=condition,
        )

    return None


def parse_attack_roll_text(text: str) -> Optional[AttackRollRule]:
    """
    Parse a hit/wound roll modifier description into a structured rule.
    Returns None unless the text is fully consumed.
    """
    norm = _normalize_text(text)
    if not norm:
        return None
    norm = re.sub(
        r"^(?:in|during) your [a-z' ]+ phase[,;:]?\s*",
        "",
        norm,
        flags=re.IGNORECASE,
    )
    norm = re.sub(r"^in addition[,;:]?\s*", "", norm, flags=re.IGNORECASE)
    norm = norm.strip()
    if not norm:
        return None

    scope = "unit"
    prefix_condition = None
    leading_contains_condition = None
    aura_range = None
    aura_faction = None
    aura_friendly = None
    m = _AURA_PREFIX_RE.match(norm)
    if m:
        scope = "aura"
        aura_friendly = m.group("aff").lower() == "friendly"
        aura_faction = m.group("faction").strip()
        aura_range = float(m.group("rng"))
        norm = norm[m.end():].strip()
    else:
        m = _LEADING_PREFIX_RE.match(norm)
        if m:
            scope = "leading"
            norm = norm[m.end():].strip()
            m_contains = re.match(
                r"^and contains (?:an?|one or more) (?P<model>.+?) models?(?:,|;|:)?\s*(?P<rest>.+)$",
                norm,
            )
            if m_contains:
                model_kw = str(m_contains.group("model") or "").strip()
                rest = str(m_contains.group("rest") or "").strip()
                cond = _parse_condition(f"this unit contains {model_kw} model")
                if cond is None:
                    return None
                leading_contains_condition = cond
                norm = rest

    norm = re.sub(r"^in addition[,;:]?\s*", "", norm, flags=re.IGNORECASE).strip()

    m = re.match(r"^(?:while|if)\s+([^,]+),\s*(.+)$", norm, flags=re.IGNORECASE)
    if m:
        cond = _parse_condition(m.group(1).strip())
        if cond is not None:
            prefix_condition = cond
            norm = m.group(2).strip()

    trigger_condition = None
    subject = ""
    attack_type = "any"
    effects_text = ""
    m = _TRIGGER_ATTACK_RE.match(norm)
    if m:
        subject = m.group("subject").strip().lower().replace(" ", "_")
        atype = (m.group("atype") or "").strip().lower()
        attack_type = atype if atype in ("melee", "ranged") else "any"
        rest = norm[m.end():].strip()
        if rest.startswith("that targets "):
            rest = rest[len("that targets "):]
            target_clause = None
            for m_comma in re.finditer(r",", rest):
                after = rest[m_comma.end():].lstrip(" ,")
                after_stripped = _strip_effect_preamble(after)
                if _EFFECT_START_RE.match(after_stripped):
                    target_clause = rest[:m_comma.start()].strip()
                    rest = after_stripped
                    break
            if not target_clause:
                m_eff = re.search(
                    r"\b(?:you can|reroll|re-?roll|add|subtract|improve|a successful|an unmodified|a critical)\b",
                    rest,
                )
                if m_eff:
                    target_clause = rest[:m_eff.start()].strip(" ,")
                    rest = rest[m_eff.start():].lstrip(" ,")
            if not target_clause:
                return None
            trigger_condition = _parse_target_clause(target_clause)
            if trigger_condition is None:
                return None
        if rest.startswith(","):
            rest = rest[1:].strip()
        effects_text = rest
    else:
        m = _TRIGGER_TARGET_WITH_ATTACK_RE.match(norm)
        if m:
            subject = m.group("subject").strip().lower().replace(" ", "_")
            atype = (m.group("atype") or "").strip().lower()
            attack_type = atype if atype in ("melee", "ranged") else "any"
            rest = norm[m.end():].strip()
            if rest.startswith(","):
                rest = rest[1:].strip()
            effects_text = rest
        else:
            m = _TRIGGER_TARGET_RE.match(norm)
            if m:
                subject = "attack_targets_unit"
                atype = (m.group("atype") or "").strip().lower()
                attack_type = atype if atype in ("melee", "ranged") else "any"
                rest = norm[m.end():].strip()
                if rest.startswith(","):
                    rest = rest[1:].strip()
                effects_text = rest
                scope = "defensive"
            else:
                return None

    def _merge_conditions(a: Optional[AttackRollCondition], b: Optional[AttackRollCondition]) -> Optional[AttackRollCondition]:
        if a is None:
            return b
        if b is None:
            return a
        return a.merge(b)

    base_condition = _merge_conditions(prefix_condition, trigger_condition)
    if leading_contains_condition is not None:
        base_condition = _merge_conditions(base_condition, leading_contains_condition)

    if subject.startswith("a_model_in_"):
        subject = subject.replace("a_model_in_", "model_in_")

    if not effects_text:
        return None

    # Some abilities combine non-roll keyword grants with roll modifiers in one clause
    # (e.g. "that attack has [SUSTAINED HITS 1] ability and add 1 to the Hit roll").
    # Strip the keyword-only fragment so hit/wound modifier parsing can proceed.
    effects_text = re.sub(
        r"^that attack has .+? abilit(?:y|ies)\s+and\s+",
        "",
        effects_text,
        flags=re.IGNORECASE,
    )
    effects_text = re.sub(
        r"\s+and\s+that attack has .+? abilit(?:y|ies)\b",
        "",
        effects_text,
        flags=re.IGNORECASE,
    )

    effects_text = _strip_punct(effects_text)
    clauses = _split_effect_clauses(effects_text)
    if not clauses:
        return None

    effects: list[AttackRollEffect] = []
    for clause in clauses:
        eff = _parse_effect_clause(clause)
        if eff is None:
            return None
        merged_cond = _merge_conditions(base_condition, eff.condition)
        effects.append(
            AttackRollEffect(
                roll=eff.roll,
                kind=eff.kind,
                value=eff.value,
                reroll_values=eff.reroll_values,
                reroll_full=eff.reroll_full,
                critical_threshold=eff.critical_threshold,
                condition=merged_cond,
            )
        )

    return AttackRollRule(
        scope=scope,
        subject=subject,
        attack_type=attack_type,
        effects=tuple(effects),
        trigger_condition=base_condition,
        aura_range=aura_range,
        aura_faction=aura_faction,
        aura_friendly=aura_friendly,
    )
