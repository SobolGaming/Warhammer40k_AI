from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Tuple


@dataclass(frozen=True)
class AttackRollCondition:
    attacker_below_starting_strength: bool = False
    attacker_below_half_strength: bool = False
    target_below_starting_strength: bool = False
    target_battleshocked: bool = False
    target_within_objective: bool = False
    target_within_range: Optional[float] = None
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
        return AttackRollCondition(
            attacker_below_starting_strength=bool(
                self.attacker_below_starting_strength or other.attacker_below_starting_strength
            ),
            attacker_below_half_strength=bool(
                self.attacker_below_half_strength or other.attacker_below_half_strength
            ),
            target_below_starting_strength=bool(
                self.target_below_starting_strength or other.target_below_starting_strength
            ),
            target_battleshocked=bool(self.target_battleshocked or other.target_battleshocked),
            target_within_objective=bool(self.target_within_objective or other.target_within_objective),
            target_within_range=merged_range,
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
    if re.fullmatch(r"that enemy unit is battle-?shocked", t):
        return AttackRollCondition(target_battleshocked=True)

    if re.fullmatch(r"(?:this model|this unit|it) is (?:also )?below (?:its )?starting strength", t):
        return AttackRollCondition(attacker_below_starting_strength=True)
    if re.fullmatch(r"(?:this model|this unit|it) is (?:also )?below half[- ]strength", t):
        return AttackRollCondition(attacker_below_half_strength=True)

    if re.fullmatch(r"that unit is (?:also )?below (?:its )?starting strength", t):
        return AttackRollCondition(attacker_below_starting_strength=True)
    if re.fullmatch(r"that unit is (?:also )?below half[- ]strength", t):
        return AttackRollCondition(attacker_below_half_strength=True)
    if re.fullmatch(r"that enemy unit is (?:also )?below (?:its )?starting strength", t):
        return AttackRollCondition(target_below_starting_strength=True)
    if re.fullmatch(r"that enemy unit is (?:also )?below half[- ]strength", t):
        return AttackRollCondition(target_below_half_strength=True)

    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*unit within range of (?:an|one or more) objective marker(?:s)?",
        t,
    ):
        return AttackRollCondition(target_within_objective=True)
    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*unit that is within range of (?:an|one or more) objective marker(?:s)?",
        t,
    ):
        return AttackRollCondition(target_within_objective=True)
    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*enemy unit within range of (?:an|one or more) objective marker(?:s)?",
        t,
    ):
        return AttackRollCondition(target_within_objective=True)
    if re.fullmatch(
        r"(?:the target of that attack|that attack) targets (?:a|an)?\s*enemy unit that is within range of (?:an|one or more) objective marker(?:s)?",
        t,
    ):
        return AttackRollCondition(target_within_objective=True)

    if re.fullmatch(r"that (?:enemy )?unit is within range of (?:an|one or more) objective marker(?:s)?", t):
        return AttackRollCondition(target_within_objective=True)

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

    if re.fullmatch(r"unit that can fly", t):
        return AttackRollCondition(target_can_fly=True)
    if re.fullmatch(r"unit that cannot fly", t):
        return AttackRollCondition(target_can_fly=False)
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
    m = re.fullmatch(r"unit \(excluding (?P<ex>[^)]+)\)", t)
    if m:
        raw = m.group("ex").replace(" and ", ",")
        parts = tuple(p.strip().lower() for p in raw.split(",") if p.strip())
        if parts:
            return AttackRollCondition(target_exclude_keywords_any=parts)
    return None


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
        r"(?:a successful|an) unmodified (?P<roll>hit|wound) roll of (?P<thresh>\d)\+ scores a critical (?P<ctype>hit|wound)",
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
        r"a critical (?P<ctype>hit|wound) is scored on an unmodified (?P<roll>hit|wound) roll of (?P<thresh>\d)\+",
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

    scope = "unit"
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
            if "," not in rest:
                return None
            target_clause, rest = rest.split(",", 1)
            trigger_condition = _parse_target_clause(target_clause)
            if trigger_condition is None:
                return None
            rest = rest.strip()
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

    if subject.startswith("a_model_in_"):
        subject = subject.replace("a_model_in_", "model_in_")

    if not effects_text:
        return None

    effects_text = _strip_punct(effects_text)
    clauses = _split_effect_clauses(effects_text)
    if not clauses:
        return None

    effects: list[AttackRollEffect] = []
    for clause in clauses:
        eff = _parse_effect_clause(clause)
        if eff is None:
            return None
        merged_cond = trigger_condition.merge(eff.condition) if (trigger_condition and eff.condition) else trigger_condition or eff.condition
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
        trigger_condition=trigger_condition,
        aura_range=aura_range,
        aura_faction=aura_faction,
        aura_friendly=aura_friendly,
    )
