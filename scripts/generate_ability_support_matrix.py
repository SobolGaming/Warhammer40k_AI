
"""
Generate docs/ABILITY_SUPPORT_MATRIX.md from Wahapedia JSON.

Output structure:
- Collapsible Core section (core abilities + core stratagems)
- Collapsible per-faction sections:
  * Army rules
  * Mustering restrictions
  * Detachments (each collapsible; abilities + restrictions + enhancements + stratagems)
  * Datasheet abilities (per faction)

Support status is derived from code (managers, explicit support lists, and pattern-based rules).
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WAHA_DIR = os.path.join(ROOT, "wahapedia_data")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "ABILITY_SUPPORT_MATRIX.md")
FACTION_DOCS_DIR = os.path.join(DOCS_DIR, "factions")

SRC_DIR = os.path.join(ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from warhammer40k_ai.utility.faction_rule_metadata import FACTION_RULE_METADATA
from warhammer40k_ai.utility.attack_roll_parser import parse_attack_roll_text
from warhammer40k_ai.roster.army import SUPPORTED_FACTION_IDS
from warhammer40k_ai.rules.stratagems import (
    IMPLEMENTED_STRATAGEM_NAMES,
    defensive_reaction_note,
    parse_charge_melee_ap_stratagem,
    parse_consolidate_move_stratagem,
    parse_defensive_reaction_stratagem,
)
from warhammer40k_ai.rules.enhancement_effects import classify_enhancement_support
from warhammer40k_ai.units.wargear import parse_alternate_3


ABILITY_SUPPORT_BY_ID: Dict[str, Tuple[str, str]] = {}
ABILITY_SUPPORT_BY_NAME_FACTION: Dict[Tuple[str, str], Tuple[str, str]] = {}
ABILITY_SUPPORT_BY_NAME_FACTION_DS: Dict[Tuple[str, str, str], Tuple[str, str]] = {}
OPTION_SUPPORT_CACHE: Dict[str, Tuple[str, str]] = {}
WARGEAR_KEYWORD_SUPPORT_CACHE: Dict[Tuple[str, Tuple[str, ...]], Tuple[str, str]] = {}
DETACHMENT_ABILITY_IDS: set[str] = set()


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _norm(text: str) -> str:
    t = str(text or "").lower()
    t = t.replace("\u2019", "'")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _norm_rules_text(text: str) -> str:
    t = _strip_html(text or "")
    t = t.replace("\u2019", "'").replace("\u0192?T", "'")
    t = re.sub(r"'s\b", "s", t)
    t = t.lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\bre roll\b", "reroll", t)
    t = re.sub(r"\bre rolls\b", "reroll", t)
    return t


def _fullmatch_tokens(pattern: str, text: str) -> bool:
    return bool(re.fullmatch(pattern, _norm_rules_text(text)))


_RULE_CLAUSE_MARKERS: tuple[str, ...] = (
    "each time",
    "first time",
    "at the start",
    "at the end",
    "once per",
    "add",
    "improve",
    "reroll",
    "re roll",
    "re-roll",
    "eligible",
    "cannot",
    "must",
    "gain",
    "gains",
    "has",
    "have",
    "roll",
    "suffer",
    "suffers",
    "choose",
    "select",
    "spend",
    "while",
    "until",
    "no ",
    "warlord",
    "points",
    "pts",
    "within",
    "destroy",
    "destroys",
    "becomes",
    "replace",
    "replacing",
    "issue",
    "orders",
)


def _strip_fluff_blocks(text: str) -> str:
    if not text:
        return ""
    # Remove explicit fluff blocks when they are marked as such in Wahapedia HTML.
    return re.sub(
        r"<p[^>]*class=\"[^\"]*(?:showfluff|legend)[^\"]*\"[^>]*>.*?</p>",
        " ",
        str(text),
        flags=re.IGNORECASE | re.DOTALL,
    )


def _rules_text_for_clauses(text: str) -> str:
    """
    Convert rich HTML rules text into a sentence-like plain text string suitable
    for clause splitting and strict consumption checks.
    """
    if not text:
        return ""
    t = html.unescape(str(text))
    t = t.replace("\u2019", "'").replace("\u0192?T", "'")
    t = _strip_fluff_blocks(t)

    # Insert separators before removing tags to preserve clause boundaries.
    for pat in (
        r"<br\s*/?>",
        r"</li>",
        r"</tr>",
        r"</td>",
        r"</p>",
        r"</div>",
        r"</ul>",
        r"</ol>",
    ):
        t = re.sub(pat, ". ", t, flags=re.IGNORECASE)
    t = re.sub(r"<li[^>]*>", " ", t, flags=re.IGNORECASE)

    # Remove remaining tags and normalize punctuation/spacing.
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[;:]+", ". ", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*\.\s*", ". ", t)
    t = re.sub(r"(?:\.\s*)+", ". ", t)
    return t.strip(" .")


def _is_rule_clause(clause_tokens: str) -> bool:
    if not clause_tokens:
        return False
    for marker in _RULE_CLAUSE_MARKERS:
        if marker in clause_tokens:
            return True
    return False


def _extract_points_cap_clauses(text: str) -> list[str]:
    """
    Extract battle-size points caps as explicit clauses so full-consumption
    checks can account for them deterministically.
    """
    if not text:
        return []
    plain = _strip_html(text or "")
    caps: list[str] = []
    for label, value in re.findall(
        r"(incursion|strike force|onslaught)\s*(?:[:\-]\s*)?(?:up to\s*)?(\d+)\s*pts",
        plain,
        flags=re.IGNORECASE,
    ):
        caps.append(_norm_rules_text(f"{label} up to {value} pts"))
    return caps


def _prey_selection_support(description: str) -> Optional[Tuple[str, str]]:
    """
    Detect BR1 prey-selection abilities (e.g., Prey of the Blood God, Psychic Spoor)
    and classify supported variants.
    """
    tokens = _norm_rules_text(description or "")
    if not tokens:
        return None
    if "start of the first battle round" not in tokens:
        return None
    if "select one enemy unit to be this models prey" not in tokens:
        return None

    repick = "prey is destroyed" in tokens and "select one new enemy unit" in tokens

    if ("melee attack" in tokens) and ("targets its prey" in tokens or "targets that prey" in tokens) and ("reroll the wound roll" in tokens):
        note = "BR1 prey selection; melee attacks vs prey can re-roll Wound rolls."
        if repick:
            note += " Re-pick when prey is destroyed."
        return ("Supported", note)

    if ("reroll the hit roll" in tokens) and ("reroll the wound roll" in tokens) and ("targets its prey" in tokens or "targets that prey" in tokens):
        note = "BR1 prey selection; attacks vs prey can re-roll Hit and Wound rolls."
        if repick:
            note += " Re-pick when prey is destroyed."
        else:
            note += " No re-pick on destruction."
        return ("Supported", note)

    if ("lethal hits" in tokens) and ("weapons equipped by models in this models unit" in tokens) and (
        "targeting this models prey" in tokens or "targets its prey" in tokens or "targets that prey" in tokens
    ):
        note = "BR1 prey selection; weapons gain [LETHAL HITS] vs prey."
        if repick:
            note += " Re-pick when prey is destroyed."
        return ("Supported", note)

    return None


def _detachment_rule_clauses(description: str) -> list[str]:
    text = _rules_text_for_clauses(description)
    if not text:
        return []
    raw_parts = [p.strip() for p in re.split(r"\.\s*", text) if p and p.strip()]
    clauses: list[str] = []
    for part in raw_parts:
        tokens = _norm_rules_text(part)
        if not tokens:
            continue
        # Ignore intermediate cap fragments; explicit cap clauses are added separately.
        if re.fullmatch(r"up to \d+ pts", tokens):
            continue
        if _is_rule_clause(tokens):
            clauses.append(tokens)

    # Include explicit points cap clauses when present.
    for cap_clause in _extract_points_cap_clauses(description):
        if cap_clause and cap_clause not in clauses:
            clauses.append(cap_clause)
    return clauses


def _detachment_full_consumption_patterns() -> Dict[str, Tuple[str, ...]]:
    """
    Clause-level full-consumption patterns for detachment abilities that we
    consider fully supported.
    """
    raw: Dict[str, Tuple[str, ...]] = {
        "Martial Grace": (
            r"at the start of the battle round you receive \d+ additional battle focus token",
            r"each time a unit from your army performs the swift as the wind agile manoeuvre until the end of the phase add an additional \d+ to the move characteristic of models in that unit",
            r"each time a unit from your army performs an agile manoeuvre that involves rolling a d6 add \d+ to the result",
        ),
        "Skilled Crews": (
            r"ranged weapons equipped by aeldari vehicle models from your army have the assault ability and you can reroll advance rolls made for aeldari vehicle fly units from your army",
            r"ranged weapons equipped by aeldari vehicle models from your army have the assault ability",
            r"you can reroll advance rolls made for aeldari vehicle fly units from your army",
        ),
        "Ruthless Discipline": (
            r"add \d+ to the number of orders each astra militarum officer model from your army can issue as stated on their datasheet",
            r"while an astra militarum unit from your army is affected by an order each time a model in that unit makes an attack reroll a hit roll of \d+",
            r"if the target of that attack is within range of an objective marker reroll a wound roll of \d+ as well",
        ),
        "Warp Rifts": (
            r"each time a legiones daemonica unit from your army is set up on the battlefield using the deep strike ability .* it can be set up anywhere that is more than 6 horizontally away from all enemy models instead of more than 9",
        ),
        "Fates in Flux": (
            r"you start the battle with three flux tokens we recommend using a dice to track how many flux tokens you have",
            r"you can spend one flux token just after an advance roll hit roll wound roll damage roll saving throw or hazardous test is made for a legiones daemonica tzeentch model or legiones daemonica tzeentch unit from your army to reroll the result of that roll throw or test",
            r"each time you spend a flux token reduce the number of flux tokens you have by one and your opponent gains one flux token",
            r"whenever your opponent has one or more flux tokens they can spend one flux token after an advance roll hit roll wound roll or saving throw is made for a model or unit from their army to reroll the result of that roll or throw",
            r"if they do they reduce the number of flux tokens they have by one and you gain one flux token",
            r"this is ignored if your opponent has the fates in flux detachment rule",
            r"in your command phase if your opponent has one or more flux tokens you gain one flux token",
            r"when using fast dice rolling this rule can be used to spend any number of flux tokens up to the amount you have to reroll a number of dice up to the amount spent after rolling multiple rolls or saving throws at once",
        ),
        "Combat Drugs": (
            r"at the start of your command phase select which combat drugs will be active for your army until the start of your next command phase",
            r"to do so either select one from the list below you cannot select the same combat drug more than once per battle or randomly select two by rolling two d6",
            r"when doing so randomly combat drugs you have previously selected can become active again but if you randomly select one that is already active for your army it has no additional effect",
            r"add \d+ to the attacks characteristic of melee weapons equipped by wych cult models from your army",
            r"add \d+ to the move characteristic of wych cult models from your army",
            r"improve the weapon skill characteristic of melee weapons equipped by wych cult models from your army by \d+",
            r"add \d+ to the toughness characteristic of wych cult models from your army",
            r"add \d+ to the strength characteristic of melee weapons equipped by wych cult models from your army",
            r"improve the leadership characteristic of wych cult models from your army by \d+ and improve the ballistic skill characteristic of ranged weapons equipped by wych cult models from your army by \d+",
        ),
        "Malefic Surge": (
            r"in your command phase one or more chaos knights units from your army can make a malefic surge",
            r"each one that does must first take a leadership test",
            r"if that test is failed that unit suffers d3 mortal wounds",
            r"then until the start of your next command phase that unit is empowered",
            r"while a unit is empowered it can use one of the malefic surge abilities below",
            r"once that unit has used a malefic surge ability it is no longer empowered",
            r"when a model in this unit makes a normal advance or fall back move until the end of the phase add 3 to its move characteristic",
            r"when this unit is selected to shoot or fight select either the lethal hits or sustained hits 1 ability",
            r"until the end of the phase weapons equipped by models in this unit have the selected ability",
            r"when this unit is selected as the target of an attack until the end of the phase select one of the following",
            r"models in this unit have a 5 invulnerable save",
            r"models in this unit have the feel no pain 6 ability",
            r"we recommend placing a token next to chaos knights models that are empowered removing it once they have used a malefic surge ability and removing all unused tokens at the start of your command phase",
        ),
        "Quicksilver Grace": (
            r"you can reroll advance rolls made for emperors children units from your army",
        ),
        "Exquisite Swordsmanship": (
            r"each time an emperors children unit from your army is selected to fight if it made a charge move this turn select one of the abilities below",
            r"while resolving those attacks melee weapons equipped by models in that unit have that ability",
        ),
        "Path of the Warrior": (
            r"each time an aspect warriors or avatar of khaine unit from your army is selected to shoot or fight select one of the following abilities for it to gain until the end of the phase",
            r"each time a model in this unit makes an attack reroll a hit roll of \d+",
            r"each time a model in this unit makes an attack reroll a wound roll of \d+",
        ),
        "Mechanised Murder": (
            r"each time an emperors children model from your army makes an attack if it is a transport model or disembarked from a transport this turn reroll a hit roll of \d+ and reroll a wound roll of \d+",
        ),
        "Daemonic Empowerment": (
            r"while an emperors children unit from your army is within 6 of one or more friendly legions of excess units it is empowered",
            r"while a legions of excess unit from your army is within 6 of one or more friendly emperor ?s children units it is empowered",
            r"while a unit from your army is empowered weapons equipped by models in that unit have the sustained hits \d+ ability",
            r"if such a weapon already has that ability each time an attack is made with that weapon an unmodified hit roll of 5 scores a critical hit",
            r"you can include legions of excess units in your army even though they do not have the emperor ?s children faction keyword",
            r"the combined points cost of such units you can include in your army is",
            r"incursion up to \d+ pts",
            r"strike force up to \d+ pts",
            r"onslaught up to \d+ pts",
            r"no legions of excess models from your army can be your warlord",
        ),
        "Pledges to the Dark Prince": (
            r"at the start of the battle round if your warlord is on the battlefield you must pledge a number to slaanesh representing how many enemy units will be destroyed this battle round",
            r"at the end of the battle round if the number of enemy units destroyed this battle round is greater than or equal to your pledge you gain a number of pact points equal to your pledge",
            r"otherwise you do not gain any pact points this battle round and your warlord model suffers d3 mortal wounds",
            r"emperors children units from your army gain a bonus depending on how many pact points you have gained during the battle as shown below these are all cumulative",
            r"pact points",
            r"each time a model in this unit makes an attack reroll a hit roll of 1",
            r"each time a model in this unit makes an attack reroll a wound roll of 1",
            r"melee weapons equipped by models in this unit have the lethal hits and sustained hits 1 abilities",
            r"each time a model in this unit makes an attack a critical hit is scored on an unmodified hit roll of 5\+?",
        ),
        "Internal Rivalries": (
            r"emperors children character units from your army can ignore any or all modifiers to their move characteristic and any or all modifiers to advance and charge rolls made for them",
            r"at the start of the battle your warlord s unit is your armys favoured champions",
            r"the first time in each players turn that an emperor ?s children character unit from your army destroys an enemy unit after resolving all of its attacks that character unit becomes your armys new favoured champions replacing the old one",
            r"each time a model in your armys favoured champions unit makes an attack you can reroll the wound roll",
        ),
        "Sensational Performance": (
            r"emperors children units from your army have the following ability",
            r"each time this unit is selected to fight if this unit made a charge move this turn it can use this ability",
            r"if it does until the end of the phase",
            r"this unit cannot target a unit it was within engagement range of at the start of the turn",
            r"this unit cannot target a unit that was the target of another units attack this phase",
            r"improve the strength and armour penetration characteristics of this units melee weapons by \d+",
        ),
        "Master of the Pageant": (
            r"once per battle round when you target a fulgrim unit from your army with the sinuous breach or prideful superiority stratagem you can reduce the cp cost of that use of that stratagem by \d+cp",
        ),
        "Fury of Titan": (
            r"each time a unit from your army is set up using the deep strike ability until the end of the turn each time a model in that unit makes an attack reroll a hit roll of \d+ and reroll a wound roll of \d+",
        ),
        "Duty Before All": (
            r"grey knights terminator units from your army are eligible to shoot and declare a charge in a turn in which they fell back",
        ),
        "Hallowed Ground": (
            r"certain areas of the battlefield are within your armys hallowed ground as follows",
            r"your deployment zone is always within your armys hallowed ground",
            r"the area of the battlefield within \d+ of one or more purifier squad units from your army is within your armys hallowed ground",
            r"at the start of any phase if you control at least half of the objective markers within no mans land until the end of that phase no mans land is within your armys hallowed ground",
            r"at the start of any phase if you control at least half of the objective markers within your opponents deployment zone until the end of that phase your opponents deployment zone is within your armys hallowed ground",
            r"each time a model in a grey knights unit from your army makes a ranged attack that targets a visible target or makes a melee attack reroll a hit roll of \d+",
            r"if that unit is a purifier squad and or is wholly within your armys hallowed ground you can reroll the hit roll instead",
        ),
        "Relentless Onslaught": (
            r"each time a necrons model from your army makes an attack that targets a unit within range of one or more objective markers add \d+ to the hit roll",
            r"in addition ranged weapons equipped by necrons vehicle and necrons mounted models excluding titanic models from your army have the assault ability",
        ),
        "Get Stuck In": (
            r"melee weapons equipped by orks models from your army have the sustained hits \d+ ability",
        ),
        "Combat Doctrines": (
            r"at the start of your command phase you can select one of the combat doctrines listed below",
            r"until the start of your next command phase that combat doctrine is active and its effects apply to all adeptus astartes units from your army",
            r"you can only select each combat doctrine once per battle",
            r"this unit is eligible to shoot in a turn in which it advanced",
            r"this unit is eligible to shoot and declare a charge in a turn in which it fell back",
            r"this unit is eligible to declare a charge in a turn in which it advanced",
        ),
        "Dutiful Tenacity": (
            r"each time an attack targets an adeptus astartes infantry or adeptus astartes mounted unit from your army if the strength characteristic of that attack is greater than the toughness characteristic of that unit subtract \d+ from the wound roll",
        ),
        "Mastered Doctrines": (
            r"at the start of up to three of your command phases you can select one of the combat doctrines listed below",
            r"until the start of your next command phase that combat doctrine is active and its effects apply to all adeptus astartes units from your army",
            r"you cannot select a combat doctrine you have already selected this battle unless a friendly marneus calgar model is on the battlefield",
            r"this unit is eligible to shoot in a turn in which it advanced",
            r"this unit is eligible to shoot and declare a charge in a turn in which it fell back",
            r"this unit is eligible to declare a charge in a turn in which it advanced",
            r"your army can include ultramarines units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "Maddened Ferocity": (
            r"each time an adeptus astartes model from your army makes a melee attack reroll a wound roll of \d+",
            r"each time an adeptus astartes unit from your army is selected to fight if that unit made a charge move this turn until the end of the phase add \d+ to the attacks characteristic of melee weapons equipped by models in that unit",
            r"if your unit is battle shocked add \d+ to the attacks characteristic of melee weapons equipped by models in that unit instead",
            r"your army can include blood angels units but it cannot include adeptus astartes units drawn from any other chapter",
        ),
        "Hyper-adaptations": (
            r"at the start of the first battle round select one of the following hyper adaptations to be active for tyranids units from your army until the end of the battle",
            r"each time a tyranids model with this hyper adaptation makes an attack that targets an infantry or swarm unit that attack has the sustained hits \d+ ability",
            r"each time a tyranids model with this hyper adaptation makes an attack that targets a monster or vehicle unit that attack has the lethal hits ability",
            r"each time a tyranids model with this hyper adaptation makes an attack that targets a character unit on a critical hit that attack has the precision ability",
        ),
        "Relentless Rage": (
            r"each time a world eaters unit from your army makes a charge move until the end of the turn add \d+ to the attacks characteristic and add \d+ to the strength characteristic of melee weapons equipped by models in that unit",
        ),
        "Blood Tithe": (
            r"each time a blood legions or world eaters unit from your army destroys an enemy unit roll one d6",
            r"on a 3 you gain 1 blood tithe point btp",
            r"at the start of the command phase you can spend one or more of your btp to activate one of the following abilities until the end of the battle",
            r"blood legions and world eaters models from your army have the feel no pain 5 ability against psychic attacks and mortal wounds",
            r"melee weapons equipped by blood legions units from your army have the lance ability",
            r"blood legions units from your army have a 4 invulnerable save",
            r"blood legions units from your army gain the blessings of khorne ability",
            r"the combined points cost of such units you can include in your army is",
            r"incursion up to \d+ pts",
            r"strike force up to \d+ pts",
            r"onslaught up to \d+ pts",
            r"no blood legions model from your army can be your warlord",
        ),
        "The Blood of Martyrs": (
            r"each time an adepta sororitas model from your army makes an attack add 1 to the hit roll if that models unit is below its starting strength and add 1 to the wound roll(?: as well)? if that models unit is below half strength",
        ),
        "Against All Odds": (
            r"each time a model in an adeptus custodes unit from your army excluding vehicles makes an attack if there are no other friendly units within \d+ of that unit add 1 to the hit roll and add 1 to the wound roll",
        ),
        "Kindred Sorcery": (
            r"in your command phase you can select one of the abilities listed below to take effect until the start of your next command phase",
            r"you can only select each of these abilities once per battle",
            r"add \d+ to the range characteristic of ranged psychic weapons equipped by thousand sons models from your army",
            r"each time a thousand sons model from your army makes an attack with a psychic weapon add \d+ to the wound roll",
            r"psychic weapons equipped by thousand sons models from your army have the devastating wounds ability",
        ),
        "All is Dust": (
            r"each time an attack with an unmodified damage characteristic of \d+ is allocated to a rubricae model from your army add \d+ to any armour saving throw made against that attack",
        ),
        "Methodical Annihilation": (
            r"each time a leagues of votann model from your army makes an attack with a weapon that targets the closest eligible target or a target that is within engagement range of that models unit",
            r"reroll a wound roll of \d+",
            r"if your unit is a k hl einhyr hearthguard or thar the destined unit improve the armour penetration characteristic of that attack by \d+",
        ),
        "Martial Leverage": (
            r"each time an enemy unit is destroyed you gain \d+yp",
        ),
        "Worldblight": (
            r"if you control an objective marker at the end of your command phase and a death guard unit from your army excluding battle shocked units is within range of that objective marker that objective marker remains under your control until your opponents level of control over that objective marker is greater than yours at the end of a phase",
            r"in addition until you lose control of that objective marker it has the nurgles gift ability as if it were a death guard model from your army",
        ),
        "Rush to the Fray": (
            r"each time a world eaters unit from your army disembarks from a transport until the end of the turn add \d+ to charge rolls made for that unit and that units melee weapons have the lance ability",
        ),
        "Wrath of Khorne": (
            r"at the start of the battle round after activating blessings of khorne you can select one or more models from your army from those listed below including models that are embarked within transports",
            r"you can select the same type of model multiple times",
            r"the maximum number of models you can select depends on the battle size as follows",
            r"until the end of the battle round each of those models has the vessel of wrath keyword we recommend marking such models with a suitable token",
            r"then select one blessing of khorne that is not currently active for your army",
            r"until the end of the battle round that blessing of khorne is active for vessel of wrath units from your army in addition to any others that are active for your army",
        ),
        "Brazen Fury": (
            r"world eaters possessed units from your army have the following ability",
            r"in your opponents shooting phase each time an enemy unit has shot if any models from this unit were destroyed as a result of those attacks this unit can make a brazen fury move",
            r"to do so roll one d6",
            r"models in this unit move a number of inches up to this result but this unit must end that move as close as possible to the closest enemy unit excluding aircraft",
            r"when doing so those models can be moved within engagement range of that enemy unit",
            r"this unit cannot make a brazen fury move while it is battle shocked or within engagement range of one or more enemy units and can only make one brazen fury move per phase",
        ),
        "Idols of Khorne": (
            r"at the start of your command phase you can select one of the idols of khorne abilities listed below",
            r"until the start of your next command phase that ability is active and its effects apply to all world eaters titanic and world eaters monster units from your army",
            r"you can only select each idols of khorne ability once per battle",
            r"while a friendly jakhals or goremongers unit is within 6 of this model or within 9 if this model is titanic each time a model in that unit makes an attack add 1 to the hit roll and add 1 to the wound roll",
            r"while a friendly jakhals or goremongers unit is within 6 of this model or within 9 if this model is titanic add 1 to the move characteristic of models in that unit and add 1 to advance and charge rolls made for that unit",
            r"while a friendly jakhals or goremongers unit is within 6 of this model or within 9 if this model is titanic models in that unit have a 4 invulnerable save",
            r"jakhals and goremongers units from your army have the battleline keyword",
        ),
    }
    return {_norm(name): tuple(pats) for name, pats in raw.items()}


def _detachment_ability_fully_consumed(name: str, description: str) -> bool:
    name_norm = _norm(name)
    patterns = _detachment_full_consumption_patterns().get(name_norm)
    if not patterns:
        return False
    clauses = _detachment_rule_clauses(description)
    if not clauses:
        return False
    unmatched = [
        clause
        for clause in clauses
        if not any(re.fullmatch(pat, clause) for pat in patterns)
    ]
    return not unmatched


def _enforce_detachment_full_consumption(status: str, notes: str, *, name: str, description: str) -> Tuple[str, str]:
    if not _status_is_supported(status):
        return status, notes
    if _detachment_ability_fully_consumed(name, description):
        return status, notes
    extra = "Full support requires consuming all rule clauses; some clauses are not fully matched."
    if notes:
        return "Partial", f"{notes} {extra}".strip()
    return "Partial", extra


def _split_attack_roll_chunks(text: str) -> tuple[list[str], list[str]]:
    cleaned = _strip_html(text or "")
    cleaned = cleaned.replace("\u2019", "'").replace("\u0192?T", "'")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return [], []
    cleaned = re.sub(r";\s*", ". ", cleaned)
    sentences = [part.strip() for part in re.split(r"\.\s*", cleaned) if part.strip()]
    if not sentences:
        return [], []

    def _effect_start(value: str) -> bool:
        return bool(
            re.match(
                r"^(?:if|add|subtract|improve|you can|reroll|re-?roll|a successful|an unmodified|a critical)\b",
                value,
                flags=re.IGNORECASE,
            )
        )

    chunks: list[str] = []
    used: set[int] = set()
    for idx, sentence in enumerate(sentences):
        if idx in used:
            continue
        sl = sentence.lower()
        if "each time" not in sl or "attack" not in sl:
            continue
        if not any(k in sl for k in ("hit roll", "wound roll", "critical", "reroll", "re-roll", "subtract", "add", "improve")):
            continue
        parts = [sentence]
        used.add(idx)
        j = idx + 1
        while j < len(sentences):
            if j in used:
                j += 1
                continue
            nxt = sentences[j].strip()
            if not nxt:
                j += 1
                continue
            if _effect_start(nxt):
                parts.append(nxt)
                used.add(j)
                j += 1
                continue
            break
        chunks.append(". ".join(parts))

    remaining = [s for i, s in enumerate(sentences) if i not in used]
    return chunks, remaining


def _cp_on_destroy_sentence(sentence: str) -> Optional[dict]:
    norm = _norm_rules_text(sentence)
    if not norm:
        return None
    pattern = (
        r"each time (?:this model|this unit|this models unit) destroys an? (?:enemy )?"
        r"(?P<kw>character|epic hero|monster|vehicle|psyker)? ?(?:model|unit)? you gain (?P<cp>\d+) ?cp"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    kw = m.group("kw")
    return {"cp": int(m.group("cp")), "keyword": kw}


def _is_kill_team_unit(name: str) -> bool:
    return _norm(name).endswith(" kill team")


def _is_virtual_datasheet(ds: dict) -> bool:
    val = str(ds.get("virtual", "") or "").strip().lower()
    return val in ("true", "1", "yes")


def _clean_cell(value: Any) -> Any:
    if isinstance(value, str):
        return _strip_html(value).replace("\u0192?T", "'").strip()
    return value


def _freeze_rows(rows: Sequence[dict], *, blacklist: set[str] | None = None) -> tuple[str, ...]:
    skip = blacklist or set()
    frozen: List[str] = []
    for row in rows or []:
        cleaned = {k: _clean_cell(v) for k, v in row.items() if k not in skip}
        if cleaned:
            frozen.append(json.dumps(cleaned, sort_keys=True, ensure_ascii=True))
    return tuple(sorted(frozen))


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = text.replace("\u2019", "'")
    text = text.replace("\u0192?T", "'")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _ascii_text(text: str) -> str:
    t = str(text or "")
    t = t.replace("\u2019", "'").replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
    t = t.replace("\u0192?T", "'")
    return t


def _escape(text: str) -> str:
    return html.escape(_ascii_text(text), quote=True)


def _status_icon(status: str) -> str:
    key = _norm(status)
    if key in ("supported", "implemented"):
        return ":green_square:"
    if key == "partial":
        return ":yellow_square:"
    return ":red_square:"


def _summary_status(supported: int, total: int) -> str:
    if total <= 0 or supported <= 0:
        return "Not implemented"
    if supported >= total:
        return "Supported"
    return "Partial"


def _summary_icon(supported: int, total: int) -> str:
    return _status_icon(_summary_status(supported, total))


def _summary_status_with_coverage(
    supported: int,
    total: int,
    det_supported: int,
    det_total: int,
    ds_supported: int,
    ds_total: int,
) -> str:
    status = _summary_status(supported, total)
    if status != "Supported":
        return status
    if det_total > 0 and det_supported < det_total:
        return "Partial"
    if ds_total > 0 and ds_supported < ds_total:
        return "Partial"
    return status


def _summary_icon_with_coverage(
    supported: int,
    total: int,
    det_supported: int,
    det_total: int,
    ds_supported: int,
    ds_total: int,
) -> str:
    return _status_icon(
        _summary_status_with_coverage(
            supported,
            total,
            det_supported,
            det_total,
            ds_supported,
            ds_total,
        )
    )


def _status_is_supported(status: str) -> bool:
    return _norm(status) in ("supported", "implemented")


def _format_units(units: Sequence[str]) -> str:
    clean = sorted({u for u in units if u}, key=lambda s: s.lower())
    if not clean:
        return "-"
    if len(clean) > 4:
        body = "<br/>".join(_escape(u) for u in clean)
        return f"<details><summary>{len(clean)} units</summary>{body}</details>"
    return ", ".join(_escape(u) for u in clean)


def _details(summary: str, body: str) -> str:
    return f"<details><summary>{_escape(summary)}</summary>{body}</details>"


def _desc_block(rules_text: str, engine_text: str) -> str:
    rules = _escape(rules_text or "-")
    engine = _escape(engine_text or "-")
    body = f"<strong>Rules:</strong> {rules}<br/><strong>Engine:</strong> {engine}"
    return _details("Description", body)

def _engine_block(engine_text: str) -> str:
    engine = _escape(engine_text or "-")
    return f"<strong>Engine:</strong> {engine}"


def _detachment_has_restrictions(det_id: str, det_name: str) -> bool:
    if str(det_id or "").strip() == "000001043":
        return False
    return True


def _normalize_token(token: str) -> str:
    t = _strip_html(token).lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .;")


def _canonical_keyword(token: str) -> str:
    t = _normalize_token(token)
    if not t:
        return ""
    if t.startswith("anti-"):
        return "anti"
    if t.startswith("rapid fire"):
        return "rapid fire"
    if t.startswith("sustained hits"):
        return "sustained hits"
    if t.startswith("melta"):
        return "melta"
    if t.startswith("feel no pain"):
        return "feel no pain"
    return t


def _keyword_support(canon: str, examples: Sequence[str]) -> Tuple[str, str]:
    c = canon.lower().strip()

    supported_notes: Dict[str, str] = {
        "assault": "Shooting after Advance is allowed for Assault profiles.",
        "blast": "Adds attacks based on target unit size.",
        "devastating wounds": "Critical wounds become mortal wounds.",
        "hazardous": "Hazardous test after attacking; on 1 suffer mortal wounds.",
        "heavy": "+1 to hit if the firing unit Remained Stationary.",
        "ignores cover": "Cancels Benefit of Cover from terrain and Indirect Fire.",
        "indirect fire": "No-LOS penalties and grants target Benefit of Cover (unless Ignores Cover).",
        "lethal hits": "Critical hits auto-wound.",
        "plunging fire": "AP improves by 1 when plunging fire conditions are met.",
        "rapid fire": "Adds attacks at half range (supports dice values like D3/D6+X).",
        "sustained hits": "Critical hits generate extra hits (supports dice values like D3/D6+X).",
        "torrent": "Auto-hits (also works under Overwatch restriction).",
        "anti": "Critical wound threshold vs matching target keyword (e.g. Anti-Infantry 4+).",
        "melta": "Adds damage at half range (supports dice values like D3/D6+X).",
        "extra attacks": "Melee selection supports 1 primary weapon plus all [EXTRA ATTACKS] weapons.",
        "one shot": "Each model can use a ONE SHOT weapon once per battle.",
        "pistol": "Engaged shooting + pistol-vs-other-ranged choice enforced.",
        "lance": "If the bearer charged this turn, +1 to wound rolls for this weapon.",
        "twin-linked": "Re-roll failed wound rolls for attacks made with this weapon.",
        "precision": "Allows allocating a successful wound to a visible CHARACTER in an Attached unit.",
        "psychic": "Tags Psychic attacks; conditional defenses (FNP/Invulnerable) check this keyword.",
        "psychic assassin": "When targeting a unit with the PSYKER keyword, this weapon's Attacks characteristic becomes 6.",
        "conversion": "Unmodified successful hits of 4+ become critical hits when the target is beyond the Conversion distance.",
        "linked fire": "Linked Fire origin selection supported; range/LOS measured from origin and Attacks=1 override applied.",
        "reverberating summons": "Weapon ability: on destroying a model, return 1 Plaguebearer model to a friendly unit within 12\".",
        # Ork-specific keywords
        "bubblechukka": "Random profile selection via D6 roll (1-2: big bubble, 3-4: wobbly bubble, 5-6: dense bubble).",
        "dead choppy": "+1 Attacks for each additional dread klaw equipped.",
        "harpooned": "Tracks hits against MONSTER/VEHICLE units for +2 charge bonus.",
        "hooked": "Tracks hits against MONSTER/VEHICLE units for +2 charge bonus and prevents Overwatch.",
        "impaled": "Tracks hits against MONSTER/VEHICLE units for +2 charge bonus.",
        "snagged": "Tracks hits against MONSTER/VEHICLE units for +2 charge bonus and prevents Overwatch.",
    }

    partial_notes: Dict[str, str] = {
        "feel no pain": "Supported as a defensive mechanic, but treated as informational here.",
    }

    if c in supported_notes:
        if c == "anti":
            for ex in examples:
                t = _normalize_token(ex)
                if t.startswith("anti-"):
                    m = re.match(r"^anti-[a-z0-9\- ]+\s+\d\+?$", t)
                    if not m:
                        return ("Partial", "Anti is implemented, but some formatting may not parse.")
        return ("Supported", supported_notes[c])

    if c in partial_notes:
        return ("Partial", partial_notes[c])

    return ("Not implemented", "No explicit gameplay effect wired for this keyword.")


def _support_for_option_desc(desc: str) -> Tuple[str, str]:
    if desc in OPTION_SUPPORT_CACHE:
        return OPTION_SUPPORT_CACHE[desc]

    dummy_unit = type("DummyUnit", (), {"models": [object() for _ in range(10)]})()
    dl = _strip_html(desc).lower()
    dl = re.sub(r"\s+", " ", dl).strip()

    if "can only be equipped with two ranged weapons if one of them is a pistol" in dl:
        result = ("Supported", "Constraint-only line: enforced (2 ranged requires 1 Pistol).")
        OPTION_SUPPORT_CACHE[desc] = result
        return result
    if "can only be equipped with two ranged weapons if one of them is a cyclone missile launcher" in dl:
        result = ("Supported", "Constraint-only line: enforced (Cyclone + Storm bolter/Combi-weapon).")
        OPTION_SUPPORT_CACHE[desc] = result
        return result
    if re.search(r"each model cannot be equipped with more than \d+ ranged weapons", dl):
        result = ("Supported", "Constraint-only line: enforced (max ranged weapons).")
        OPTION_SUPPORT_CACHE[desc] = result
        return result
    if re.search(r"(?:no model|this model) can(?:not)? be equipped with both .+ and .+", dl):
        result = ("Supported", "Constraint-only line: enforced (mutual exclusion).")
        OPTION_SUPPORT_CACHE[desc] = result
        return result
    if re.search(r"cannot be equipped with more than \d+ [\w\s\-']+", dl):
        result = ("Supported", "Constraint-only line: enforced (max weapon counts).")
        OPTION_SUPPORT_CACHE[desc] = result
        return result
    if "a model can only take one of these options" in dl or "cannot be equipped with more than one of these wargear options" in dl:
        result = ("Supported", "Constraint-only line: enforced (model option mutex).")
        OPTION_SUPPORT_CACHE[desc] = result
        return result
    if dl.startswith("*"):
        if "these options cannot be taken on the same model" in dl:
            result = ("Supported", "Footnote: enforced (per-model option mutex).")
            OPTION_SUPPORT_CACHE[desc] = result
            return result
        if "cannot have duplicates of these pieces of wargear" in dl:
            result = ("Supported", "Footnote: enforced (no duplicates in choice list).")
            OPTION_SUPPORT_CACHE[desc] = result
            return result
        if "cannot be replaced" in dl:
            result = ("Supported", "Footnote: enforced (replacement lock).")
            OPTION_SUPPORT_CACHE[desc] = result
            return result
        if "this weapon cannot be replaced" in dl:
            result = ("Supported", "Footnote: enforced (replacement lock for selected item).")
            OPTION_SUPPORT_CACHE[desc] = result
            return result
        if "helbrute fist cannot then be replaced" in dl:
            result = ("Supported", "Footnote: enforced (replacement lock).")
            OPTION_SUPPORT_CACHE[desc] = result
            return result
        if "to a maximum of" in dl:
            result = ("Supported", "Footnote: enforced (max-per-models ratio).")
            OPTION_SUPPORT_CACHE[desc] = result
            return result
        if "maximum 1 per model" in dl or "maximum one per model" in dl:
            result = ("Supported", "Footnote: enforced (max 1 per model).")
            OPTION_SUPPORT_CACHE[desc] = result
            return result
        if "you cannot select the same weapon" in dl or "you cannot select the same option" in dl:
            result = ("Supported", "Footnote: enforced (unit selection caps).")
            OPTION_SUPPORT_CACHE[desc] = result
            return result
        if "you cannot select both of these options for the same model" in dl:
            result = ("Supported", "Footnote: enforced (per-model option mutex).")
            OPTION_SUPPORT_CACHE[desc] = result
            return result
        if "the rules for a watcher in the dark can be found" in dl:
            result = ("Supported", "Informational footnote (no gameplay enforcement needed).")
            OPTION_SUPPORT_CACHE[desc] = result
            return result
        if "designer" in dl and "note" in dl:
            result = ("Supported", "Designer note (no gameplay enforcement needed).")
            OPTION_SUPPORT_CACHE[desc] = result
            return result
    if "this weapon cannot be replaced" in dl:
        result = ("Supported", "Footnote: enforced (replacement lock).")
        OPTION_SUPPORT_CACHE[desc] = result
        return result

    try:
        parsed = parse_alternate_3([desc], dummy_unit)
    except Exception:
        result = ("Not implemented", "Parser raised while interpreting this option text.")
        OPTION_SUPPORT_CACHE[desc] = result
        return result
    if not parsed:
        result = ("Not implemented", "Parser could not interpret this option text.")
        OPTION_SUPPORT_CACHE[desc] = result
        return result

    hard_conditional_markers = (
        "excluding ",
        "maximum of",
    )

    for opt in parsed:
        conds = " | ".join(getattr(opt, "conditionals", []) or []).lower()
        if any(m in conds for m in hard_conditional_markers):
            result = ("Partial", "Parsed, but has constraints not fully enforced.")
            OPTION_SUPPORT_CACHE[desc] = result
            return result

        item_max = getattr(getattr(opt, "item_quantity", None), "max", 1)
        if item_max and int(item_max) > 1:
            if "item_limit is equal to number of equipped" not in conds:
                result = ("Partial", "Parsed, but allows selecting multiple items (needs stronger enforcement).")
                OPTION_SUPPORT_CACHE[desc] = result
                return result

        choices = list(getattr(opt, "wargear_to", []) or [])
        if len(choices) > 1:
            seen = set()
            for choice in choices:
                key = tuple(sorted((int(qty), (str(nm or "").lower().strip())) for qty, nm in (choice or []) if nm))
                if key in seen:
                    result = ("Partial", "Parsed, but contains duplicate identical choices.")
                    OPTION_SUPPORT_CACHE[desc] = result
                    return result
                seen.add(key)

    result = ("Supported", "Parsed and selectable with current mechanisms (best-effort).")
    OPTION_SUPPORT_CACHE[desc] = result
    return result


def _damaged_profile_pattern_key(desc: str) -> str:
    t = _strip_html(desc)
    t = t.replace("\u2019", "'").replace("\u0192?T", "'")
    t = re.sub(r"\s+", " ", t).strip()
    parts: List[str] = []

    rx_hit_minus = re.compile(r"subtract\s+(\d+)\s+from\s+the\s+hit\s+roll", re.IGNORECASE)
    rx_oc_minus = re.compile(
        r"subtract\s+(\d+)\s+from\s+(?:this\s+(?:model|unit)'?s|its)\s+objective\s+control\s+characteristic",
        re.IGNORECASE,
    )
    rx_half_attacks = re.compile(
        r"halve\s+the\s+attacks\s+characteristic|attacks\s+characteristics\s+of\s+all\s+of\s+its\s+weapons\s+are\s+halved",
        re.IGNORECASE,
    )
    rx_add_attacks_melee = re.compile(
        r"add\s+(\d+)\s+to\s+the\s+attacks\s+characteristic\s+of\s+this\s+model'?s\s+melee\s+weapons",
        re.IGNORECASE,
    )
    rx_add_attacks_weapon = re.compile(
        r"add\s+(\d+)\s+to\s+the\s+attacks\s+characteristic\s+of\s+this\s+model'?s\s+([a-z0-9 \-']+)",
        re.IGNORECASE,
    )
    rx_relics_limit = re.compile(r"relics\s+of\s+the\s+matriarchs.*only\s+select\s+one\s+ability", re.IGNORECASE)

    if rx_hit_minus.search(t):
        parts.append("Hit roll -N")
    if rx_oc_minus.search(t):
        parts.append("OC -N")
    if rx_half_attacks.search(t):
        parts.append("Halve Attacks")
    if rx_add_attacks_melee.search(t):
        parts.append("Melee Attacks +N")
    else:
        m = rx_add_attacks_weapon.search(t)
        if m and "melee weapons" not in t.lower():
            wname = (m.group(2) or "").strip().lower()
            if wname and wname not in ("weapons", "weapon"):
                parts.append("Specific weapon Attacks +N")
    if rx_relics_limit.search(t):
        parts.append("Limit Relics of the Matriarchs choices")
    if not parts:
        return "Other / unclassified"
    return " + ".join(parts)


def _damaged_profile_support_for_key(key: str) -> Tuple[str, str]:
    supported = {
        "Hit roll -N": "Applies a damaged-profile to-hit modifier (-N) with normal +/-1 cap handling.",
        "OC -N": "Applies an additive Objective Control penalty while damaged.",
        "Halve Attacks": "Halves weapon attacks while damaged (round up).",
        "Hit roll -N + OC -N": "Applies both -N to hit and OC penalty.",
        "Hit roll -N + Halve Attacks": "Applies both -N to hit and halved attacks.",
        "Hit roll -N + OC -N + Halve Attacks": "Applies all three effects while damaged.",
        "Melee Attacks +N": "Adds +N attacks for melee weapons while damaged.",
        "Specific weapon Attacks +N": "Adds +N attacks for a named weapon while damaged (best-effort match).",
    }
    if key in supported:
        return ("Supported", supported[key])
    if "Limit Relics of the Matriarchs choices" in key:
        return ("Partial", "Flag stored, but no gameplay/UI consumption yet.")
    if key == "Other / unclassified":
        return ("Not implemented", "No parser/engine effect wired for this damaged profile text.")
    return ("Partial", "Some damaged-profile text is recognized, but not all effects are implemented.")


def _points_support(entries: Sequence[dict]) -> Tuple[str, str]:
    if not entries:
        return ("Not implemented", "No points data.")

    base: Dict[int, int] = {}
    addons: Dict[str, int] = {}
    unparsed = 0
    range_lines = 0

    for entry in entries:
        desc = str(entry.get("description", "") or "").strip()
        cost_raw = str(entry.get("cost", "") or "").strip()
        if not desc and not cost_raw:
            continue
        if re.search(r"\d+\s*[-\u2013]\s*\d+", desc) or "to a maximum" in desc.lower():
            range_lines += 1

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

        m = re.match(r"^\+?\s*(\d+)\s*$", cost_raw)
        if m and desc:
            addons[desc.lower()] = int(m.group(1))
            continue

        unparsed += 1

    if not base:
        return ("Not implemented", "No base points parsed.")
    if unparsed or range_lines:
        bits = []
        if unparsed:
            bits.append(f"{unparsed} unparsed line(s)")
        if range_lines:
            bits.append(f"{range_lines} range line(s)")
        return ("Partial", ", ".join(bits))

    return ("Supported", f"{len(base)} cost bucket(s)")

def _is_spawn_only_datasheet(ability_entries: Sequence[dict], points_entries: Sequence[dict]) -> bool:
    if points_entries:
        return False
    for entry in (ability_entries or []):
        name = str(entry.get("name", "") or "").strip()
        if _norm(name) == "using sir hekhtur":
            return True
    return False


def _keywords_support(entries: Sequence[dict]) -> Tuple[str, str]:
    if not entries:
        return ("Not implemented", "No keywords data.")

    keywords = []
    faction_keywords = []
    for row in entries:
        kw = str(row.get("keyword", "") or "").strip()
        if not kw:
            continue
        is_faction = str(row.get("is_faction_keyword", "") or "").strip().lower() == "true"
        if is_faction:
            faction_keywords.append(kw)
        else:
            keywords.append(kw)

    if not keywords and not faction_keywords:
        return ("Not implemented", "No keywords detected.")
    if not keywords:
        return ("Partial", "Missing non-faction keywords.")
    if not faction_keywords:
        return ("Partial", "Missing faction keywords.")
    return ("Supported", f"{len(keywords)} keywords, {len(faction_keywords)} faction keyword(s)")


def _parse_attribute_value(value: str) -> Optional[int]:
    if value is None:
        return None
    s = str(value).replace("\"", "").replace("+", "").replace("*", "").strip()
    if not s:
        return None
    if s in ("-", "—"):
        return 0
    if "-" in s:
        return None
    try:
        return int(s)
    except Exception:
        return None


def _base_size_parseable(value: str) -> bool:
    if value is None:
        return False
    s = str(value).strip().lower()
    if not s:
        return False
    if "use model" in s or "no official base size" in s:
        return True
    if "flying base" in s:
        s = s.replace("flying base", "").strip()
    if "x" in s:
        return True
    return bool(re.search(r"\d+\s*mm", s))


def _models_support(entries: Sequence[dict]) -> Tuple[str, str]:
    if not entries:
        return ("Not implemented", "No model profiles.")

    missing = 0
    invalid = 0
    for row in entries:
        for field in ("M", "T", "Sv", "W", "Ld", "OC"):
            if not str(row.get(field, "") or "").strip():
                missing += 1
                continue
            if _parse_attribute_value(row.get(field)) is None:
                invalid += 1
        if not _base_size_parseable(row.get("base_size")):
            missing += 1

    if missing or invalid:
        bits = []
        if missing:
            bits.append(f"{missing} missing field(s)")
        if invalid:
            bits.append(f"{invalid} invalid field(s)")
        return ("Partial", ", ".join(bits))
    return ("Supported", f"{len(entries)} model profile(s)")


def _unit_composition_support(entries: Sequence[dict]) -> Tuple[str, str]:
    if not entries:
        return ("Not implemented", "No unit composition.")

    def _split_top_level_commas(text: str) -> List[str]:
        parts: List[str] = []
        buf: List[str] = []
        depth = 0
        for ch in text:
            if ch == "(":
                depth += 1
            elif ch == ")" and depth > 0:
                depth -= 1
            if ch == "," and depth == 0:
                seg = "".join(buf).strip()
                if seg:
                    parts.append(seg)
                buf = []
            else:
                buf.append(ch)
        tail = "".join(buf).strip()
        if tail:
            parts.append(tail)
        return parts

    def _split_top_level_and(text: str) -> List[str]:
        parts: List[str] = []
        buf: List[str] = []
        depth = 0
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")" and depth > 0:
                depth -= 1
            if depth == 0 and text[i : i + 5].lower() == " and ":
                nxt = text[i + 5 : i + 15].lstrip()
                if nxt and re.match(r"^\d", nxt):
                    seg = "".join(buf).strip()
                    if seg:
                        parts.append(seg)
                    buf = []
                    i += 5
                    continue
            buf.append(ch)
            i += 1
        tail = "".join(buf).strip()
        if tail:
            parts.append(tail)
        return parts

    parsed = 0
    unparsed = 0
    for row in entries:
        desc = str(row.get("description", "") or "").strip()
        if not desc:
            continue
        dlow = desc.strip().rstrip(".").lower()
        if dlow in ("or", "or:"):
            continue
        if dlow.startswith("this unit can contain a maximum of "):
            continue
        if dlow.endswith("models maximum"):
            continue

        segments = []
        for seg in _split_top_level_commas(desc):
            segments.extend(_split_top_level_and(seg))

        for seg in segments:
            seg = seg.strip().rstrip(".")
            if not seg:
                continue
            m = re.match(r"^(?P<count>\d+(?:-\d+)?)\s+(?P<name>.+)$", seg)
            if m:
                parsed += 1
            else:
                unparsed += 1

    if parsed == 0:
        return ("Not implemented", "No parsable composition entries.")
    if unparsed:
        return ("Partial", f"{unparsed} unparsed line(s)")
    return ("Supported", f"{parsed} composition line(s)")


def _transport_support(text: str) -> Tuple[str, str]:
    t = _strip_html(text)
    if not t:
        return ("Supported", "No transport rules.")
    patterns = [
        r"transport\s+capacity\s+(?:of\s+)?(\d+)",
        r"transport\s*capacity\s*[:\-]\s*(\d+)",
        r"\btransport\s*\(?\s*(\d+)\s*\)?\b",
    ]
    for pat in patterns:
        if re.search(pat, t, flags=re.IGNORECASE):
            return ("Supported", "Transport capacity parsed.")
    return ("Partial", "Transport rules present but capacity unparsed.")


def _other_sections_support(
    *,
    unit_comp_entries: Sequence[dict],
    model_entries: Sequence[dict],
    transport_text: str,
) -> Tuple[str, str]:
    comp_status, comp_note = _unit_composition_support(unit_comp_entries)
    model_status, model_note = _models_support(model_entries)
    transport_status, transport_note = _transport_support(transport_text)

    notes = []
    for label, status, note in (
        ("Unit composition", comp_status, comp_note),
        ("Models", model_status, model_note),
        ("Transport", transport_status, transport_note),
    ):
        if status != "Supported":
            notes.append(f"{label}: {note}")

    if comp_status == "Not implemented" or model_status == "Not implemented" or transport_status == "Not implemented":
        return ("Not implemented", "; ".join(notes))
    if comp_status == "Partial" or model_status == "Partial" or transport_status == "Partial":
        return ("Partial", "; ".join(notes))
    return ("Supported", "Core datasheet sections parsed.")


def _abilities_support_summary(statuses: Sequence[str]) -> Tuple[str, str]:
    total = len(list(statuses or []))
    supported = sum(1 for s in statuses if _status_is_supported(s))
    partial = sum(1 for s in statuses if _norm(s) == "partial")
    not_impl = total - supported - partial

    if total == 0:
        return ("Not implemented", "No datasheet abilities.")
    if supported == 0 and partial == 0:
        return ("Not implemented", f"{not_impl}/{total} not implemented")
    if supported == total and partial == 0:
        return ("Supported", f"{supported}/{total} supported")
    return ("Partial", f"{supported}/{total} supported, {partial} partial, {not_impl} not implemented")


def _optional_wargear_support(entries: Sequence[dict]) -> Tuple[str, str]:
    if not entries:
        return ("Supported", "No optional wargear.")

    statuses = []
    for row in entries:
        desc = str(row.get("description", "") or "")
        status, _note = _support_for_option_desc(desc)
        statuses.append(status)

    total = len(statuses)
    supported = sum(1 for s in statuses if _status_is_supported(s))
    partial = sum(1 for s in statuses if _norm(s) == "partial")
    not_impl = total - supported - partial

    if supported == 0 and partial == 0:
        return ("Not implemented", f"{not_impl}/{total} not implemented")
    if supported == total and partial == 0:
        return ("Supported", f"{supported}/{total} supported")
    return ("Partial", f"{supported}/{total} supported, {partial} partial, {not_impl} not implemented")


def _wargear_keywords_support(entries: Sequence[dict]) -> Tuple[str, str]:
    if not entries:
        return ("Supported", "No wargear keywords.")

    examples_by_canon: Dict[str, set] = {}
    for row in entries:
        desc = str(row.get("description", "") or "")
        if not desc:
            continue
        desc_text = _strip_html(desc)
        parts = [p.strip() for p in re.split(r"\s*,\s*|\s*;\s*|\s+\.\s+", desc_text) if p.strip()]
        for raw in parts:
            canon = _canonical_keyword(raw)
            if not canon:
                continue
            examples_by_canon.setdefault(canon, set()).add(raw)

    if not examples_by_canon:
        return ("Supported", "No wargear keywords.")

    statuses: Dict[str, str] = {}
    for canon, examples in examples_by_canon.items():
        key = (canon, tuple(sorted(examples)))
        if key in WARGEAR_KEYWORD_SUPPORT_CACHE:
            status, _note = WARGEAR_KEYWORD_SUPPORT_CACHE[key]
        else:
            status, _note = _keyword_support(canon, list(examples))
            WARGEAR_KEYWORD_SUPPORT_CACHE[key] = (status, _note)
        statuses[canon] = status

    total = len(statuses)
    supported = sum(1 for s in statuses.values() if _status_is_supported(s))
    partial = sum(1 for s in statuses.values() if _norm(s) == "partial")
    not_impl = total - supported - partial

    if supported == 0 and partial == 0:
        return ("Not implemented", f"{not_impl}/{total} not implemented")
    if supported == total and partial == 0:
        return ("Supported", f"{supported}/{total} supported")

    partial_names = sorted([k for k, v in statuses.items() if _norm(v) == "partial"])
    not_impl_names = sorted([k for k, v in statuses.items() if _norm(v) == "not implemented"])
    bits = [f"{supported}/{total} supported"]
    if partial_names:
        sample = ", ".join(partial_names[:3])
        tail = "..." if len(partial_names) > 3 else ""
        bits.append(f"partial: {sample}{tail}")
    if not_impl_names:
        sample = ", ".join(not_impl_names[:3])
        tail = "..." if len(not_impl_names) > 3 else ""
        bits.append(f"not implemented: {sample}{tail}")
    return ("Partial", "; ".join(bits))


def _datasheet_support_status(
    *,
    faction_id: str,
    datasheet_name: str,
    categories: Sequence[Tuple[str, str, str]],
    overrides: Dict[Tuple[str, str], Tuple[str, str]],
) -> Tuple[str, str]:
    fid = str(faction_id or "").strip().upper()
    key = (fid, _norm(datasheet_name))
    if key in overrides:
        return overrides[key]

    statuses = [status for _label, status, _note in categories]
    if all(_status_is_supported(s) for s in statuses):
        overall = "Supported"
    elif any(_norm(s) == "not implemented" for s in statuses):
        overall = "Not implemented"
    else:
        overall = "Partial"

    notes = []
    for label, status, note in categories:
        if _status_is_supported(status):
            continue
        if note:
            notes.append(f"{label}: {note}")
        else:
            notes.append(f"{label}: {status}")

    if not notes:
        return (overall, "Fully supported.")
    return (overall, "; ".join(notes))

def _ability_id_support_by_name() -> Dict[str, Tuple[str, str]]:
    raw = {
        "Acts of Faith": ("Supported", "Miracle dice pool with per-phase Act usage and substitution tracking."),
        "Martial Ka'tah": ("Supported", "Fight-phase Ka'tah selection with Lethal/Sustained hit hooks."),
        "Doctrina Imperatives": ("Supported", "Round-based imperatives with WS/BS/AP/heavy/assault modifiers."),
        "Voice of Command": ("Supported", "Order issuing in Command phase with stat modifiers."),
        "Gate of Infinity": ("Supported", "Teleport eligible units with placement validation."),
        "Assigned Agents": ("Supported", "Imperial Agents ally caps enforced by battle size."),
        "Code Chivalric": ("Supported", "Deed/Quality tracking with on-roll effects."),
        "Bondsman": ("Supported", "Bondsman buffs applied to Armiger units."),
        "Super-heavy Walker": ("Supported", "Move-through models (excl. TITANIC), engagement pass-through, tall-terrain Battle-shock check."),
        "Battle Focus": ("Supported", "Token system + maneuver selection with per-phase limits."),
        "Power from Pain": ("Supported", "Pain token engine with full Pain ability coverage."),
        "Cult Ambush": ("Supported", "Resurgence points, ambush markers, reinforcements."),
        "Prioritised Efficiency": ("Supported", "Yield points + mode tracking with objective checks."),
        "Reanimation Protocols": ("Supported", "Command-phase reanimation sequencing for Necrons."),
        "Waaagh!": ("Supported", "Once-per-battle Waaagh effects tracked and applied."),
        "For the Greater Good": ("Supported", "Observer/Guided targeting with markerlight bonuses."),
        "Synapse": ("Supported", "Synapse aura checks via distance rules."),
        "Shadow in the Warp": ("Supported", "Once-per-battle armywide Battle-shock trigger."),
        "The Shadow of Chaos": ("Supported", "Shadow zones + manifestations/terror handling."),
        "Harbingers of Dread": ("Supported", "Dread ability selection and aura checks."),
        "Dark Pacts": ("Supported", "Dark Pacts selection with lethal/sustained hooks."),
        "Nurgle's Gift (Aura)": ("Supported", "Contagion range + plague effects."),
        "Thrill Seekers": ("Supported", "EC core rule hooks for crits and movement bonuses."),
        "Pact of Decay": ("Supported", "Army faction restriction enforced during validation."),
        "Pact of Excess": ("Supported", "Army faction restriction enforced during validation."),
        "Pact of Sorcery": ("Supported", "Army faction restriction enforced during validation."),
        "Pact of Blood": ("Supported", "Army faction restriction enforced during validation."),
        "Cabal of Sorcerers": ("Supported", "Cabal rituals and warp charge checks."),
        "Blessings of Khorne": ("Supported", "Blessings dice engine + effects."),
        "Oath of Moment": ("Supported", "Target selection + hit/wound bonuses."),
        "Templar Vows": ("Supported", "Vow selection with combat/objective effects."),
        "Leader": ("Supported", "Attach Leaders during battle formations; protect Characters until Bodyguard is gone."),
        "Deep Strike": ("Supported", "Reserves placement in Reinforcements step; enforces >9\" distance."),
        "Feel No Pain": ("Supported", "Post-damage roll to ignore wounds, including mortals."),
        "Fights First": ("Supported", "Fight phase sequencing uses Fights First step."),
        "Fight on Death": ("Supported", "Destroyed units can fight after attacker resolves."),
        "Shoot on Death": ("Supported", "Destroyed units can shoot after attacker resolves."),
        "Firing Deck": ("Supported", "Transports fire with selected embarked weapons; marks passengers as shot."),
        "Infiltrators": ("Supported", "Forward deploy placement >9\" from enemy zone/models."),
        "Lone Operative": ("Supported", "Ranged targeting blocked beyond 12\" when not Attached."),
        "Scouts": ("Supported", "Pre-game Scout move, including transport use when applicable."),
        "Stealth": ("Supported", "Apply -1 to hit vs ranged attacks."),
        "Deadly Demise": ("Supported", "On destruction, roll 6+ to deal mortals within 6\"."),
        "Plunging Fire": ("Supported", "Extra AP vs targets below attacker elevation."),
        "Hover": ("Supported", "Declare Hover at battle formations; Move set to 20\" and AIRCRAFT keyword removed."),
    }
    return {_norm(name): val for name, val in raw.items()}


def _detachment_ability_support_by_name() -> Dict[str, Tuple[str, str]]:
    raw = {
        "Against All Odds": (
            "Supported",
            "Lions of the Emperor: non-vehicle ADEPTUS CUSTODES units gain +1 to hit and +1 to wound when no other friendly units are within 6\" (3D; attached units deduplicated).",
        ),
        "Kindred Sorcery": (
            "Supported",
            "Grand Coven: Command-phase selection (once per battle per option) with Imbued Manifestation (+6\" Psychic ranged weapons), Psychic Maelstrom (+1 to wound with Psychic weapons), and Wrath of the Immaterium ([Devastating Wounds] on Psychic weapons).",
        ),
        "All is Dust": (
            "Supported",
            "Rubricae Phalanx: Rubricae models gain +1 to armour saves against attacks with unmodified Damage 1.",
        ),
        "Methodical Annihilation": (
            "Supported",
            "Hearthband: re-roll Wound rolls of 1 when targeting the closest eligible target or a target within Engagement Range; Kahl/Einhyr Hearthguard/Uthar units also improve AP by 1 (attached units inherit this bonus).",
        ),
        "Martial Leverage": (
            "Supported",
            "Needgaârd Oathband: gain 1 Yield Point each time an enemy unit is destroyed (integrates with Prioritised Efficiency).",
        ),
        "Worldblight": (
            "Supported",
            "Virulent Vectorium: qualifying objectives become sticky until opponent OC is greater at end of a phase, and remain Nurgle's Gift contagion sources while controlled.",
        ),
        "Quicksilver Grace": ("Supported", "Mercurial Host: reroll Advance rolls for eligible units."),
        "Exquisite Swordsmanship": ("Supported", "Peerless Bladesmen: on charge choose Lethal or Sustained for melee."),
        "Mechanised Murder": ("Supported", "Rapid Evisceration: reroll Hit/Wound rolls of 1 for eligible units."),
        "Daemonic Empowerment": ("Supported", "Carnival of Excess: empowered units gain Sustained Hits."),
        "Skilled Crews": (
            "Supported",
            "Armoured Warhost: AELDARI VEHICLE ranged weapons count as [ASSAULT]; AELDARI VEHICLE FLY units can re-roll Advance rolls.",
        ),
        "Path of the Warrior": (
            "Supported",
            "Aspect Host: select re-roll Hit 1s or re-roll Wound 1s each time an Aspect Warriors or Avatar of Khaine unit is selected to shoot or fight (until end of phase).",
        ),
        "Pledges to the Dark Prince": (
            "Supported",
            "Coterie of the Conceited: start-of-round pledge decision, destroyed-unit tracking, end-of-round resolution, and pact point bonuses are implemented.",
        ),
        "Internal Rivalries": (
            "Supported",
            "Slaanesh's Chosen: Move/Advance/Charge modifier-ignore choices, Favoured Champions switching after attacks resolve, and favoured champions wound re-rolls are implemented.",
        ),
        "Sensational Performance": ("Supported", "Court of the Phoenician: optional +1 S/AP on charge."),
        "Master of the Pageant": ("Supported", "Court of the Phoenician: once per round -1 CP stratagem cost."),
        "Relentless Rage": ("Supported", "Berzerker Warband: on charge, melee weapons gain +1A/+2S until end of turn."),
        "Brazen Fury": (
            "Supported",
            "Possessed Slaughterband: on opponent shooting casualties, eligible WORLD EATERS POSSESSED can Brazen Fury (D6) toward closest non-AIRCRAFT enemy; once per phase; blocked if Battle-shocked or engaged.",
        ),
        "Rush to the Fray": (
            "Supported",
            "Goretrack Onslaught: disembarking WORLD EATERS units gain +1 to charge rolls and melee weapons gain [LANCE] until end of turn.",
        ),
        "Wrath of Khorne": (
            "Supported",
            "Vessels of Wrath: after Blessings of Khorne, select up to battle-size cap eligible models (including embarked) to gain VESSEL OF WRATH; pick one non-active Blessing to apply to VESSEL OF WRATH units for the battle round.",
        ),
        "Idols of Khorne": (
            "Supported",
            "Cult of Blood: Command-phase selection (once per idol per battle) activates one Idol aura for WORLD EATERS TITANIC/MONSTER sources; JAKHALS/GOREMONGERS within 6\" (9\" if source is TITANIC) gain either +1 hit/+1 wound, +1\" Move/+1 Advance/+1 Charge, or a 4+ invulnerable save. JAKHALS/GOREMONGERS gain BATTLELINE.",
        ),
        "Get Stuck In": ("Supported", "War Horde: ORKS melee weapons gain Sustained Hits 1."),
        "Combat Doctrines": ("Supported", "Gladius Task Force: select each doctrine once per battle to grant move/charge eligibility."),
        "Mastered Doctrines": (
            "Supported",
            "Blade of Ultramar: up to three Command phase doctrine selections; doctrine reuse requires Marneus Calgar on the battlefield; doctrine effects and Ultramarines-only chapter restriction enforced.",
        ),
        "Dutiful Tenacity": (
            "Supported",
            "Wrath of the Rock: ADEPTUS ASTARTES INFANTRY/MOUNTED units take -1 to wound when attacked by higher Strength.",
        ),
        "Combat Drugs": (
            "Supported",
            "Spectacle of Spite: select one Combat Drug (once per drug per battle) or roll 2D6 to apply two; "
            "Wych Cult models gain the corresponding bonuses until your next Command phase.",
        ),
        "Malefic Surge": (
            "Supported",
            "Infernal Lance: Command-phase unit selection with Leadership test + D3 mortals on failure; Empowered state grants Unholy Hunger (+3\" Move), Diabolic Power (Lethal or Sustained Hits 1), or Unnatural Fortitude (5+ invuln or FNP 6+), then consumes Empowered.",
        ),
        "Blood Tithe": (
            "Supported",
            "Khorne Daemonkin: gain BTP on 3+ for eligible kills; spend BTP to activate Enraged Abjuration, Daemonic Rage, Boon of Blood, or Might of Khorne (command phase limit + A Worthy Skull fight-phase activation). Restriction enforced during army validation.",
        ),
        "Duty Before All": (
            "Supported",
            "Hallowed Conclave: GREY KNIGHTS TERMINATOR units can shoot and charge after Falling Back.",
        ),
        "Fury of Titan": (
            "Supported",
            "Brotherhood Strike: Deep Strike arrivals re-roll Hit and Wound rolls of 1 until end of turn.",
        ),
        "Hallowed Ground": (
            "Supported",
            "Warpbane Task Force: Hallowed Ground zones (own deployment zone always, 6\" of PURIFIER SQUAD units, "
            "phase-start control of No Man's Land/opponent deployment zone objectives) grant GREY KNIGHTS hit re-rolls "
            "of 1 on visible ranged attacks or melee; PURIFIER SQUAD or units wholly within Hallowed Ground can re-roll "
            "the Hit roll instead.",
        ),
        "Warp Rifts": (
            "Supported",
            "Daemonic Incursion: Deep Strike min distance reduced to 6\" when wholly within Shadow of Chaos zones or within 6\" of a matching Greater Daemon/Dark Master aura; cannot bootstrap off the arriving unit.",
        ),
        "Fates in Flux": (
            "Supported",
            "Scintillating Legion: Flux tokens tracked and transferable; TZEENTCH LEGIONES DAEMONICA units can spend tokens for Advance/Hit/Wound/Save/Damage/Hazardous re-rolls (multi-die selections supported), opponents can spend tokens on Advance/Hit/Wound/Save re-rolls unless they also have Fates in Flux, and Command phase token gain applies when the opponent has tokens.",
        ),
        "Martial Grace": ("Supported", "Warhost: +1 Battle Focus token; Swift as the Wind +1\" move; +1 to D6 Agile Manoeuvre rolls."),
        "Relentless Onslaught": ("Supported", "Starshatter Arsenal: +1 to hit vs targets within objective range; VEHICLE/MOUNTED (non-TITANIC) ranged weapons gain Assault."),
        "Ruthless Discipline": (
            "Supported",
            "Grizzled Company: OFFICERs issue +1 order; ordered units re-roll Hit rolls of 1 and re-roll Wound rolls of 1 vs targets within objective range.",
        ),
        "The Blood of Martyrs": (
            "Supported",
            "Hallowed Martyrs: ADEPTA SORORITAS models gain +1 to hit below Starting Strength and +1 to wound below Half-strength.",
        ),
        "Maddened Ferocity": (
            "Supported",
            "Rage-cursed Onslaught: melee attacks re-roll Wound rolls of 1; on fight selection, +1A if charged or +2A if Battle-shocked.",
        ),
        "Hyper-adaptations": (
            "Supported",
            "Invasion Fleet: select one Hyper-adaptation at battle round 1; applies Sustained Hits 1 vs INFANTRY/SWARM, Lethal Hits vs MONSTER/VEHICLE, or Precision on crits vs CHARACTER.",
        ),
    }
    return {_norm(name): val for name, val in raw.items()}


def _restriction_support_by_name() -> Dict[str, Tuple[str, str]]:
    raw = {
        "Freeblades": ("Supported", "Imperial Knights ally and detachment restrictions enforced."),
        "Disparate Paths": ("Supported", "Harlequin/Ynnari ally validation in mustering."),
        "Corsairs and Travelling Players": ("Supported", "Corsairs/Travelling Players ally limits enforced."),
        "Daemonic Pact": ("Supported", "Chaos Daemon ally validation with caps and keyword rules."),
        "Dreadblades": ("Supported", "Chaos Knights ally validation and model caps."),
        "Cult of the Dark Gods": ("Supported", "Cult ally points caps and keyword adjustments."),
        "Pact of Decay": ("Supported", "Army faction restriction enforced during validation."),
        "Pact of Excess": ("Supported", "Army faction restriction enforced during validation."),
        "Pact of Sorcery": ("Supported", "Army faction restriction enforced during validation."),
        "Pact of Blood": ("Supported", "Army faction restriction enforced during validation."),
        "Space Marine Chapters": ("Supported", "Chapter keyword restrictions and unit bans."),
        "Deathwatch": ("Supported", "Deathwatch-only chapter restrictions."),
        "You can include the BLOOD LEGIONS units in your army. The combined points cost of such units you can include in your army is: Incursion: Up to 500 pts Strike Force: Up to 1000 pts Onslaught: Up to 1500 pts No BLOOD LEGIONS model from your army can be your WARLORD.": (
            "Supported",
            "BLOOD LEGIONS points caps enforced by battle size; BLOOD LEGIONS cannot be your WARLORD.",
        ),
    }
    return {_norm(name): val for name, val in raw.items()}


def _datasheet_ability_support_global() -> Dict[str, Tuple[str, str]]:
    raw = {
        "Supreme Commander": ("Supported", "If any SUPREME COMMANDER unit is in the army, one must be the Warlord."),
        "One Shot": ("Supported", "Weapon-level one-shot tracking enforced per model."),
        "Super-heavy Walker": ("Supported", "Move-through models (excl. TITANIC), engagement pass-through, tall-terrain Battle-shock check."),
        "Super-heavy War Engine": ("Supported", "Move-through models (excl. TITANIC), engagement pass-through, tall-terrain Battle-shock check."),
        "Collar of Khorne": ("Supported", "Feel No Pain 3+ against Psychic attacks."),
        "Flip Belt": ("Supported", "Ignore vertical distance for Move/Advance/Fall Back/Charge movement."),
        "Conversion": ("Supported", "Conversion keyword supported: 4+ successful hits become critical hits beyond the Conversion distance."),
        "Reverberating Summons": (
            "Supported",
            "Weapon ability: when this weapon destroys a model, select a friendly Plaguebearers unit within 12\" to return 1 destroyed model.",
        ),
        "Fortification": (
            "Supported",
            "Enemy units only in Engagement Range of friendly Fortifications can be targeted by ranged attacks (non-Pistol: -1 to hit) and skip Battle-shocked fall back escape tests unless moving over enemies.",
        ),
    }
    return {_norm(name): val for name, val in raw.items()}


def _datasheet_ability_support_by_name_faction() -> Dict[Tuple[str, str], Tuple[str, str]]:
    raw = {
        ("AS", "Endless Suffering"): ("Supported", "Charge-after-Advance eligibility."),
        ("AS", "Holy Mission"): ("Partial", "Scouts/Infiltrators applied without attachment restriction."),
        ("AS", "Holy Vanguard"): ("Partial", "Scouts 6\" applied without attached/embarked restriction."),
        ("AS", "Null Rod"): ("Supported", "Feel No Pain 4+ against mortal wounds and Psychic attacks."),
        ("AS", "Rituale Nullificatus"): ("Supported", "Feel No Pain 4+ against Psychic attacks and mortal wounds."),
        ("AS", "Spiritual Fortitude"): ("Supported", "Feel No Pain 4+ against Psychic attacks and mortal wounds."),
        ("QT", "Taskmaster (Aura)"): ("Supported", "WAR DOG models within 9\" re-roll Hit rolls of 1 for ranged attacks."),
        ("QT", "Frenzied Rampage (Aura)"): ("Supported", "WAR DOG models within 9\" re-roll Hit rolls of 1 for melee attacks."),
        ("CD", "Shadow of Khorne (Aura)"): (
            "Supported",
            "Shadow of Chaos extends within 6\" of the fortification; friendly KHORNE LEGIONES DAEMONICA units within 6\" can re-roll Battle-shock tests.",
        ),
        ("CD", "Symphony of Pain (Psychic)"): (
            "Supported",
            "End of Movement: select a Battle-shocked enemy within 12\"; friendly SLAANESH LEGIONES DAEMONICA models re-roll Hit and Wound rolls vs that unit until end of turn.",
        ),
        ("CD", "Grotesque Regeneration"): (
            "Supported",
            "End of each phase: each damaged Beasts of Nurgle model regains all lost wounds.",
        ),
        ("QT", "Dread Dominion (Aura)"): ("Supported", "WAR DOG models within 9\" improve Leadership by 1 and gain +1 OC."),
        ("QT", "Close-range Killers (Aura)"): ("Supported", "WAR DOG attacks vs closest enemy improve AP by 1 while within 9\"."),
        ("QT", "Infernal Aegis (Aura)"): ("Supported", "WAR DOG models within 6\" gain the Benefit of Cover."),
        ("QT", "Methodical Destruction"): ("Supported", "Select a victim at BR1; reroll Wound rolls vs victim; re-pick on victim destroyed."),
        ("AC", "Daughter of the Abyss"): ("Supported", "Feel No Pain 3+ against Psychic attacks and mortal wounds."),
        ("AC", "Daughters of the Abyss"): ("Supported", "Feel No Pain 3+ against Psychic attacks and mortal wounds."),
        ("AC", "Captain-General"): (
            "Supported",
            "Leading: attacks can ignore any/all Ballistic/Weapon Skill modifiers and Hit roll modifiers (per-attack choice).",
        ),
        ("AC", "Corner the Quarry"): (
            "Supported",
            "Enemy non-MONSTER/VEHICLE units within Engagement Range that Fall Back take Desperate Escape tests; Battle-shocked targets suffer -1.",
        ),
        ("AC", "From Golden Light"): (
            "Supported",
            "Once per battle: end of opponent's turn, if not in Engagement Range, unit may enter Strategic Reserves.",
        ),
        ("AC", "Golden Laurels"): ("Supported", "Leading: melee attacks targeting the unit worsen AP by 1."),
        ("AC", "Hero of Lion's Gate"): (
            "Supported",
            "Once per battle, after a hit/wound/save roll for this model, change the result to an unmodified 6.",
        ),
        ("AC", "Living Fortress"): (
            "Supported",
            "Once per battle at the start of any phase, models in this unit gain Feel No Pain 4+ until end of phase.",
        ),
        ("AC", "Martial Inspiration"): ("Supported", "Once-per-battle advance-and-charge eligibility enforced."),
        ("AC", "Master of the Stances"): (
            "Supported",
            "Once per battle, when selected to fight, both Martial Ka'tah stances are active.",
        ),
        ("AC", "Moment Shackle"): (
            "Supported",
            "Once per battle, start of Fight phase: choose Watcher's Axe Attacks 12 or 2+ invulnerable save until end of phase.",
        ),
        ("AC", "Praesidium Shield"): ("Supported", "Bearer gains +1 Wounds."),
        ("AC", "Purity of Execution"): ("Supported", "Ranged attacks vs PSYKER units gain [PRECISION] and [DEVASTATING WOUNDS]."),
        ("AC", "Quicksilver Execution"): (
            "Supported",
            "Once per battle: after Normal/Advance move, select a moved-over enemy (non MONSTER/VEHICLE); roll one D6 per model, 2+ inflicts 2 mortal wounds.",
        ),
        ("AC", "Sanctified Flames"): ("Supported", "After shooting, select a hit enemy unit to take a Battle-shock test."),
        ("AC", "Strike from the Skies"): ("Supported", "Shoot and charge after Falling Back."),
        ("AC", "Sweeping Advance"): (
            "Supported",
            "Once per battle, end of Fight phase after unit fights: Fall Back if engaged, otherwise Normal move.",
        ),
        ("AC", "Tactical Perception"): ("Supported", "Leading: unit gains Fights First."),
        ("CD", "Cruel Hunter"): ("Supported", "Leading: pile-in/consolidate up to 6\"."),
        ("CD", "A Gory Path"): ("Supported", "Consolidate up to 6\"."),
        ("CD", "Jolly Gutpipes"): (
            "Supported",
            "Leading: bearer unit gains +1 Move and can re-roll Advance rolls.",
        ),
        ("CD", "Blood Throne"): (
            "Supported",
            "Start of Fight phase: select an enemy within range (and visibility when specified); friendly KHORNE LEGIONES DAEMONICA attacks vs that unit gain +1S/+1AP/+1D until end of phase.",
        ),
        ("CD", "Champion Slayer"): (
            "Supported",
            "Re-roll Wound rolls vs CHARACTER/MONSTER targets; heal D6 lost wounds when destroying a CHARACTER/MONSTER unit.",
        ),
        ("CD", "Harbinger of Death"): (
            "Supported",
            "Selected to fight: choose Lethal Hits, Precision, or Sustained Hits 1 for hellforged weapons until end of phase.",
        ),
        ("CD", "Malefic Destruction"): (
            "Supported",
            "Once per battle, start of Fight phase: hellforged weapons gain +3 Attacks until end of phase.",
        ),
        ("CD", "The Eternal Dance"): (
            "Supported",
            "Start of Fight phase: select enemy within 6\"; friendly SLAANESH LEGIONES DAEMONICA melee attacks gain +1 to wound and that enemy's melee attacks suffer -1 to wound.",
        ),
        ("CD", "Tormentbringer (Aura)"): (
            "Supported",
            "Friendly SLAANESH LEGIONES DAEMONICA units within 6\" grant Sustained Hits 1 to their melee weapons.",
        ),
        ("CD", "Beast Handler"): ("Supported", "Leading: re-roll Charge rolls; once per battle Heroic Intervention for 0CP."),
        ("CD", "Devastating Charge"): ("Supported", "Charge end: enemy units in Engagement Range take Battle-shock tests."),
        ("CD", "Skullmaster\u2019s Fury"): ("Supported", "Charge end: Juggernaut's bladed horns gain [DEVASTATING WOUNDS]."),
        ("CD", "Deluge of Nurgle (Aura)"): ("Supported", "Enemy within 6\" suffers -2 Move and -1 OC."),
        ("CD", "Nurgle\u2019s Rot (Psychic)"): ("Supported", "End of Movement: select enemy within 12\"; -1 Toughness until next Movement."),
        ("CD", "Seed the Garden of Nurgle"): ("Supported", "End of Movement: Area Terrain counts as within Shadow of Chaos."),
        ("CD", "Rider of the Immaterial Winds"): ("Supported", "Once per battle: end of opponent turn, enter Strategic Reserves."),
        ("CD", "Blazing Warpfire (Psychic)"): ("Supported", "Leading: unit ranged weapons gain Assault."),
        ("CD", "Flames of Change (Psychic)"): (
            "Supported",
            "Post-shoot: select a hit enemy non-MONSTER/VEHICLE unit, roll 1D6; on 4+, it is aflame until end of opponent's next turn (-2\" Move, -2 Advance, -2 Charge).",
        ),
        ("CD", "Eldritch Flames (Psychic)"): (
            "Supported",
            "Post-shoot: select a hit enemy unit; it cannot gain Benefit of Cover until end of phase.",
        ),
        ("CD", "Death\u2019s Heads"): (
            "Supported",
            "Post-shoot: select a hit enemy unit; friendly keyword units re-roll Wound rolls vs that unit until end of turn.",
        ),
        ("CD", "Mischief and Confusion"): (
            "Supported",
            "Start of opponent Shooting: select a visible enemy within 12\"; roll D6 (2-5: -1 to hit; 6: not eligible to shoot) until phase end.",
        ),
        ("CD", "Horrible Fascination(Psychic)"): (
            "Supported",
            "Start of opponent Shooting: select a visible enemy within 12\"; roll D6 (1: Psyker suffers D3 MW; 2-5: -1 to hit; 6: not eligible to shoot) until phase end.",
        ),
        ("CD", "Fluxmaster"): ("Supported", "Leading: attacks against the unit suffer -1 to hit."),
        ("CD", "Cover"): (
            "Supported",
            "Fortification: if target is not fully visible due to this Fortification, it gains Benefit of Cover against the attack.",
        ),
        ("CD", "Diseased Cover"): (
            "Supported",
            "Fortification: if target is not fully visible due to this Fortification, it gains Benefit of Cover against the attack.",
        ),
        ("CD", "Master of Magicks (Psychic)"): (
            "Supported",
            "Shooting phase: choose Ignores Cover, Lethal Hits, or Sustained Hits D3 for Bolt of Change until end of phase.",
        ),
        ("CD", "Warp Strike"): ("Supported", "End of Fight: if destroyed an enemy unit and not engaged, enter Strategic Reserves."),
        ("CD", "Mischief Makers"): (
            "Supported",
            "Enemy non-TITANIC units selected to fight while engaged suffer -1 to hit with melee attacks until end of phase.",
        ),
        ("CD", "Formless Horror"): (
            "Supported",
            "Each time an enemy unit wishes to target The Changeling, it must take a Battle-shock test; on failure it cannot target The Changeling for the rest of the phase.",
        ),
        ("CD", "Hysterical Frenzy (Psychic)"): (
            "Supported",
            "Fight phase: after a SLAANESH LEGIONES DAEMONICA unit is targeted, select a nearby Psyker to enable fight-on-death on a 4+ for destroyed models until end of phase.",
        ),
        ("CD", "Virulent Blessing (Psychic)"): (
            "Supported",
            "Start of Fight: select a visible enemy within 24\"; NURGLE LEGIONES DAEMONICA attacks allocated to that unit gain +1 Damage until end of phase.",
        ),
        ("CSM", "Cruel Hunter"): ("Supported", "Leading: pile-in/consolidate up to 6\"."),
        ("CSM", "Chance for Glory"): (
            "Supported",
            "Once per battle, start of Fight phase: improve S/A/AP/D of the bearer's melee weapons by 1 until end of phase.",
        ),
        ("CSM", "Despoilers"): ("Supported", "After making a Dark Pact, unit re-rolls Hit rolls until end of phase."),
        ("CSM", "Unholy Bloodshed"): (
            "Supported",
            "Once per battle, when making a Dark Pact, unit weapons gain [DEVASTATING WOUNDS] until end of phase.",
        ),
        ("CSM", "Malign Sacrifice"): (
            "Supported",
            "Start of Fight phase: select a Dark Disciple and an enemy within Engagement Range, roll D6 (2-5=1 MW, 6=D3 MW) and destroy the Disciple.",
        ),
        ("CSM", "Sacrificial Dagger"): (
            "Supported",
            "Once per phase on being selected to shoot or fight: unit suffers 1 MW; bearer gains +1 to hit/wound with Psychic attacks until end of phase.",
        ),
        ("CSM", "Gift of Chaos (Psychic)"): (
            "Supported",
            "After resolving attacks, select a unit hit by the bearer's Psychic attacks to take a Leadership test or suffer D3 MW.",
        ),
        ("CSM", "Death Hex (Psychic)"): (
            "Supported",
            "Start of Shooting: select a visible enemy within 12\"; roll D6 (1: Psyker unit suffers D3 MW; 2+: attacks vs target improve AP by 1) until next Movement phase.",
        ),
        ("CSM", "Swift Assault"): ("Supported", "Leading: unit ranged weapons gain Assault."),
        ("CSM", "Warp Strike"): ("Supported", "End of Fight: if destroyed an enemy unit and not engaged, enter Strategic Reserves."),
        ("ADM", "Dynamic Efficiency"): ("Partial", "Charge-after-Advance/Fall Back supported; Desperate Escape rerolls not implemented."),
        ("ADM", "Elevated Strider"): ("Partial", "Shoot-after-Fall-Back/Advance supported; Desperate Escape rerolls not implemented."),
        ("ADM", "Enginseer"): ("Partial", "Lone Operative applied without 3\" Vehicle proximity or leading restriction."),
        ("ADM", "Mechanicus Bodyguard"): ("Supported", "Conditional Lone Operative within 3\" of friendly ADEPTUS MECHANICUS units."),
        ("ADM", "Shroudpsalm (Aura)"): ("Partial", "Stealth applied to bearer only; aura not propagated."),
        ("AM", "Alchemyk Counteragents"): ("Supported", "Feel No Pain 6+ against mortal wounds."),
        ("AM", "Desert Riders"): ("Partial", "Shoot and charge after Falling Back; ignores Move/Advance/Charge modifiers not handled."),
        ("AM", "Enginseer"): ("Supported", "Conditional Lone Operative within 3\" of friendly ASTRA MILITARUM VEHICLE units."),
        ("AM", "Horsemasters"): ("Supported", "Shoot and charge after Falling Back."),
        ("AM", "Malign Wardings(Psychic)"): ("Supported", "Leading: Feel No Pain 4+ against Psychic attacks."),
        ("GK", "Indomitable Spirit (Psychic)"): ("Supported", "Shoot and charge after Advance/Fall Back."),
        ("GK", "Retinue"): ("Partial", "Deep Strike granted without leading restriction; Teleport Assault not implemented."),
        ("GK", "Sanctic Hood"): ("Supported", "Leading: Feel No Pain 4+ against Psychic attacks."),
        ("GK", "Techmarine"): ("Supported", "Conditional Lone Operative within 3\" of friendly GREY KNIGHTS VEHICLE units."),
        ("GK", "Truesilver Aegis (Aura)"): ("Partial", "Feel No Pain 6+ against mortal wounds applies to bearer only; aura not propagated."),
        ("GK", "Untouchable Purity"): ("Partial", "Feel No Pain 4+ against mortal wounds applied without leading restriction."),
        ("GK", "Haloed in Soulfire (Psychic)"): (
            "Supported",
            "Leading: attached unit can only be targeted by ranged attacks within 18\".",
        ),
        ("AOI", "Abomination"): ("Supported", "Feel No Pain 2+ against Psychic attacks."),
        ("AOI", "Backroom Deals"): ("Partial", "Infiltrators applied without formation selection/leading restriction."),
        ("AOI", "Frenzon"): ("Supported", "Shoot and charge after Advancing."),
        ("AOI", "Psychic Hood"): ("Supported", "Feel No Pain 4+ against Psychic attacks."),
        ("AOI", "Rites of Teleportation"): ("Partial", "Deep Strike granted without Inquisitor attachment restriction."),
        ("AOI", "Unsubtle Crusader"): ("Partial", "Scouts 6\" applied without formation selection/target-unit restriction."),
        ("AE", "ASPECT TRAINING"): (
            "Supported",
            "Leading: grants Fights First when attached to Howling Banshees; grants Infiltrators/Scouts 7\"/Stealth when attached to Striking Scorpions.",
        ),
        ("AE", "Aspect Shrine Token"): (
            "Supported",
            "Per-roll prompt lets non-CHARACTER models change a hit or wound roll to an unmodified 6, consuming a token; tokens tracked from wargear options with per-activation prompt suppression.",
        ),
        ("AE", "Psychic Communion (Psychic)"): (
            "Supported",
            "Selected to shoot: per Warlock model, Destructor gains +A/+S for each other friendly Aeldari Psyker within 6\" (max +2).",
        ),
        ("AE", "Psychic Guidance"): (
            "Supported",
            "Within 12\" of friendly AELDARI PSYKER: Leadership set to 6+; Wraithlord improves BS/WS by 1; Wraithguard/Wraithblades add +1 to hit.",
        ),
        ("AE", "Way of the Blade"): ("Supported", "Leading: unit gains Fights First."),
        ("AE", "Empowered by Death"): ("Partial", "Fights First applied without below-strength condition."),
        ("AE", "Spiritseer"): ("Supported", "Conditional Lone Operative within 3\" of friendly WRAITH CONSTRUCT units."),
        ("AE", "Bonesinger"): ("Partial", "Lone Operative applied without 3\" proximity/leading restrictions."),
        ("AE", "Superlative Strategist"): ("Supported", "Leading: re-roll Advance rolls; re-roll any rolls while performing an Agile Manoeuvre."),
        ("AE", "Linked Fire"): ("Supported", "Linked Fire origin selection supported; range/LOS measured from origin and Attacks=1 override applied."),
        ("AE", "Choreographer of War"): (
            "Supported",
            "Leading: pile-in/consolidate up to 6\" and must end as close as possible to the closest enemy unit.",
        ),
        ("AE", "Cegorach's Favour"): (
            "Supported",
            "Once per turn: first failed saving throw for the bearer's unit sets that attack's Damage to 0.",
        ),
        ("AE", "Channeller Stones"): (
            "Supported",
            "Once per turn: first failed saving throw for the bearer's unit sets that attack's Damage to 0.",
        ),
        ("AE", "Dance of Death"): (
            "Supported",
            "Leading: at the start of the Fight phase choose Hero's Prowess (re-roll hit 1s), Villain's Doom (+1 to wound), or Trickster's Grace (-1 to hit vs the unit).",
        ),
        ("AE", "Cruel Amusement"): (
            "Supported",
            "Selected to shoot: choose Ignores Cover, Precision, or Sustained Hits 3 for the shrieker cannon until end of phase.",
        ),
        ("AE", "Cloudstrider"): ("Supported", "Leading: optional 6\" Deep Strike placement; no charge that turn."),
        ("AE", "Cry of the Wind"): (
            "Supported",
            "On set up: until end of the turn, successful unmodified hit rolls with ranged attacks count as critical hits.",
        ),
        ("SM", "Lead From the Front"): ("Partial", "Leading: unit ranged weapons gain Assault; Scouts 6\" not implemented."),
        ("SM", "Swift Assault"): ("Supported", "Leading: unit ranged weapons gain Assault."),
        ("SM", "Wind Walker (Psychic)"): (
            "Supported",
            "Leading: unit ranged weapons gain Assault; Advance roll replaced with +6\" Move this phase.",
        ),
        ("SM", "For the Khan!"): ("Partial", "Leading: unit ranged weapons gain Assault; melee weapons gaining Lance not implemented."),
        ("SM", "Icon of Old Caliban (Aura)"): ("Partial", "Stealth aura within 6\" supported; Benefit of Cover aura not implemented."),
        ("TAU", "Coldstar Commander"): ("Supported", "Leading: Move characteristic set to 12\"; unit ranged weapons gain Assault."),
        ("AE", "Empyric Ambush"): ("Supported", "Leading: unit can declare a charge in a turn it used Flickerjump."),
        ("AE", "Cluster Caltrops"): ("Supported", "Re-roll move-over mortal wound dice (one per model with Cluster Caltrops)."),
        ("AE", "SERVANT OF THE WHISPERING GOD"): ("Supported", "Ynnari Epic Hero restriction enforced during army validation."),
        ("AE", "AVATAR OF THE WHISPERING GOD"): ("Supported", "Ynnari Epic Hero restriction enforced during army validation."),
        ("AE", "Acrobatic"): ("Supported", "Charge-after-Advance/Fall Back eligibility."),
        ("AE", "Blur of Movement"): ("Supported", "Charge-after-Advance eligibility."),
        ("AE", "War Construct"): ("Supported", "Shoot after Falling Back."),
        ("AE", "Flawless Poise"): ("Supported", "Shoot and charge after Falling Back."),
        ("AE", "Into the Foe"): ("Partial", "Charge-after-Advance applies to the transport; disembark timing/target unit requirement not enforced."),
        ("AE", "SUPPORT ARTILLERY"): (
            "Supported",
            "Declare Battle Formations: Support Weapon can join one Guardian Defenders unit (max 1), counts as part of that unit, and joined unit cannot embark.",
        ),
        ("AE", "Support Weapon"): (
            "Supported",
            "When targeted, if the unit contains other models, the Support Weapon model uses Toughness 3 for that attack.",
        ),
        ("AE", "Structural Collapse"): (
            "Supported",
            "D-cannon attacks re-roll Damage rolls of 1; vs TITANIC targets you can re-roll the Damage roll instead.",
        ),
        ("AE", "Treacherous Illusion (Psychic)"): (
            "Supported",
            "Enemy melee weapons targeting this unit gain Hazardous.",
        ),
        ("AE", "Ethereal Form"): (
            "Supported",
            "Each time this model destroys an enemy unit, it regains D3 lost wounds (no choice; capped by missing wounds).",
        ),
        ("AE", "Scattershield"): (
            "Supported",
            "Bearer has a 4+ invulnerable save and reduces allocated attack damage by 1.",
        ),
        ("AE", "Shadow Field"): (
            "Supported",
            "Bearer cannot re-roll invulnerable saves; first failed invulnerable save breaks the invulnerable save for the rest of the battle.",
        ),
        ("AE", "Crystalline Targeting"): (
            "Supported",
            "After shooting: select a hit enemy unit; friendly AELDARI attacks vs it improve AP by 1 until end of phase (per-target once per turn).",
        ),
        ("AE", "Whispering Web"): (
            "Supported",
            "After shooting: select a hit enemy unit; friendly keyword attacks score critical hits on X+ vs that unit until end of turn.",
        ),
        ("AE", "Death is Not Enough"): (
            "Supported",
            "After shooting: select a hit enemy unit (excluding MONSTER/VEHICLE) to take a Battle-shock test; apply the on-kill modifier if triggered.",
        ),
        ("AE", "Sonic Destruction"): (
            "Supported",
            "Vibro cannon attacks gain +S/AP/D per other friendly platform that targeted the same enemy unit this phase.",
        ),
        ("AE", "Fog of Dreams (Psychic)"): (
            "Supported",
            "Leading: attached unit can only be targeted by ranged attacks within 18\".",
        ),
        ("AE", "Polychromatic Camouflage"): (
            "Supported",
            "Ranged attacks can only target this unit within 18\".",
        ),
        ("AE", "Whirling Death"): (
            "Supported",
            "Leading: Advance without roll; +6\" Move; ignore vertical distance during Advance moves.",
        ),
        ("AE", "Tactical Acumen"): (
            "Supported",
            "Leading: after shooting, unit can make a Normal move up to X\" and cannot charge that turn.",
        ),
        ("AE", "Spirit Mark (Psychic)"): (
            "Supported",
            "Movement phase: select friendly WRAITH CONSTRUCT within range and a visible enemy; Sustained Hits vs that enemy until your next Movement phase.",
        ),
        ("AE", "Tears of Isha (Psychic)"): (
            "Supported",
            "Command phase: select friendly WRAITH CONSTRUCT within range; return 1 destroyed model (optional) or heal D3; each unit once per turn.",
        ),
        ("AE", "Word of the Phoenix (Psychic)"): (
            "Supported",
            "Leading: in your Command phase, on 2+ return D3+1 destroyed bodyguard models (excluding support weapon models).",
        ),
        ("AE", "Face of Death"): (
            "Supported",
            "After shooting: select a hit enemy unit to take a Battle-shock test at -1.",
        ),
        ("AE", "Fire Support"): (
            "Supported",
            "After shooting: select a hit enemy unit; friendly units disembarked from this transport re-roll Wound rolls vs it until end of phase.",
        ),
        ("AE", "Fleet of Foot"): (
            "Supported",
            "Fade Back Agile Manoeuvre without spending a Battle Focus token; does not consume phase maneuver usage.",
        ),
        ("AE", "Hand of Asuryan"): (
            "Supported",
            "Once per battle (when selected to shoot): Bloody Twins Damage 3 and gains ANTI-INFANTRY 5+ and DEVASTATING WOUNDS until end of phase.",
        ),
        ("AE", "Harvester of Souls"): (
            "Supported",
            "Leading: after selecting targets (single target), roll D6 for that unit and enemies within 3\"; on 5+ they suffer D3 mortal wounds after attacks.",
        ),
        ("AE", "Herald of Ynnead"): (
            "Supported",
            "Start of Fight phase: select engaged enemy unit; friendly AELDARI re-roll Wound rolls of 1 vs it until phase end.",
        ),
        ("AE", "Misfortune (Psychic)"): (
            "Supported",
            "End of Movement phase: select visible enemy within 18\"; that unit suffers -1 to wound rolls until your next Command phase (per-target once per turn).",
        ),
        ("AE", "Monofilament Web"): (
            "Supported",
            "After shooting with doomweaver hits, target is pinned (-2 Move/-2 Charge) until your next turn.",
        ),
        ("AE", "Piratical Raiders"): (
            "Supported",
            "Start of battle: select an enemy unit; this unit's weapons gain Lethal Hits and Precision vs that unit.",
        ),
        ("AE", "Point-blank Devastation"): (
            "Supported",
            "Within half range: can re-roll attack dice for heavy wraithcannon or suncannon.",
        ),
        ("CD", "Bounding Leaps"): ("Supported", "Shoot after Falling Back."),
        ("CD", "Chosen Marauders"): ("Supported", "Shoot and charge after Advance/Fall Back."),
        ("CD", "Brass Collar of Bloody Vengeance"): ("Supported", "Feel No Pain 3+ against Psychic attacks and mortal wounds."),
        ("CD", "One Head Looks Forward"): ("Supported", "End of Command phase: Leadership test for the model; gain 1CP on pass."),
        ("CD", "DAEMONIC ALLEGIANCE"): (
            "Supported",
            "Muster: select a god keyword; keyword-only selection supported and Soul Grinder wargear applied when present.",
        ),
        ("CD", "Daemon Prince of Khorne"): ("Supported", "If KHORNE: hellforged weapons gain +2 Strength."),
        ("CD", "Daemon Prince of Tzeentch"): ("Supported", "If TZEENTCH: infernal cannon gains +3 Attacks."),
        ("CD", "Daemon Prince of Nurgle"): ("Supported", "If NURGLE: model Toughness +1."),
        ("CD", "Daemon Prince of Slaanesh"): ("Supported", "If SLAANESH: model Move +2\"."),
        ("CD", "Daemonic Lord"): ("Supported", "Conditional Lone Operative within 3\" of friendly LEGIONES DAEMONICA INFANTRY units."),
        ("CD", "Daemon Lord of Khorne (Aura)"): ("Supported", "+1 to hit (melee) aura within 6\" for KHORNE LEGIONES DAEMONICA."),
        ("CD", "Rage Embodied (Aura)"): ("Supported", "+1 Attacks for melee weapons within 6\" for KHORNE LEGIONES DAEMONICA."),
        ("CD", "Prince of Darkness (Aura)"): ("Supported", "Stealth aura within 6\" for LEGIONES DAEMONICA units."),
        ("CD", "Shroud of Flies (Aura)"): ("Supported", "Stealth aura within 6\" for NURGLE LEGIONES DAEMONICA units."),
        ("CD", "Split"): (
            "Supported",
            "Queued after attack resolution: 4+ spawns 2 Blue for destroyed Pink, or 1 Brimstone for destroyed Blue; placement handled.",
        ),
        ("CD", "Sullen Malevolence (Aura)"): (
            "Supported",
            "Enemy units within 6\" suffer Leadership +1 while the unit contains Blue Horrors and Blue abilities are active.",
        ),
        ("CD", "Exploding Horrors"): (
            "Supported",
            "Fight selection: choose engaged enemy and Brimstones; each 4+ destroys a Brimstone and deals 1 mortal.",
        ),
        ("CD", "HORRORS ARE PINK. HORRORS ARE BLUE. WHEREONCE THERE WAS ONE, NOW THERE ARE TWO."): (
            "Supported",
            "When no Pink Horrors remain, unit swaps to Blue Horrors datasheet; Blue abilities are suppressed while Pink models remain.",
        ),
        ("CD", "Shadow Form"): ("Supported", "Shadow Form selection each battle round with active effect tracking."),
        ("CD", "Wreathed in Shadows (Aura, Psychic)"): ("Supported", "18\" ranged targeting restriction while within 6\" of active Shadow Form source."),
        ("CD", "Pall of Despair (Aura, Psychic)"): ("Supported", "Forces Battle-shock tests for Below Starting Strength units within 9\" in opponent Command phase; heals on failed tests."),
        ("CD", "Shadow Lord (Aura, Psychic)"): ("Supported", "Re-roll Hit rolls of 1 aura within 6\" while active."),
        ("CD", "The Dark Master (Aura)"): ("Supported", "Area within 6\" counts as Shadow of Chaos."),
        ("CD", "Greater Daemon of Khorne (Aura)"): (
            "Supported",
            "Friendly KHORNE LEGIONES DAEMONICA units within 6\" count as within your army's Shadow of Chaos.",
        ),
        ("CD", "Greater Daemon of Nurgle (Aura)"): (
            "Supported",
            "Friendly NURGLE LEGIONES DAEMONICA units within 6\" count as within your army's Shadow of Chaos.",
        ),
        ("CD", "Greater Daemon of Slaanesh (Aura)"): (
            "Supported",
            "Friendly SLAANESH LEGIONES DAEMONICA units within 6\" count as within your army's Shadow of Chaos.",
        ),
        ("CD", "Greater Daemon of Tzeentch (Aura)"): (
            "Supported",
            "Friendly TZEENTCH LEGIONES DAEMONICA units within 6\" count as within your army's Shadow of Chaos.",
        ),
        ("CD", "Monarch of the Hunt"): ("Supported", "Quarry selection + melee reroll hooks vs quarry."),
        ("CD", "No Prey Can Evade"): ("Supported", "Re-roll Advance and Charge rolls."),
        ("CD", "Unholy Speed"): ("Supported", "Re-roll Advance and Charge rolls."),
        ("CD", "Pack Leader"): ("Supported", "Leading: re-roll Advance and Charge rolls for the unit."),
        ("CSM", "Warpsmith"): ("Supported", "Conditional Lone Operative within 3\" of friendly HERETIC ASTARTES VEHICLE units."),
        ("CSM", "Indentured Daemon Engines"): ("Supported", "Conditional Lone Operative within 3\" of friendly DAEMON VEHICLE units."),
        ("CSM", "Chosen Marauders"): ("Supported", "Shoot and charge after Advance/Fall Back."),
        ("CSM", "Hovering Death"): ("Supported", "Shoot and charge after Falling Back."),
        ("EC", "Daemon Primarch of Slaanesh"): ("Supported", "Opponent Command phase selection of Beguiling Form, Daemonic Speed, or Enthralling Hypnosis until the next opponent Command phase."),
        ("EC", "Daemonic Poisons"): ("Supported", "After shooting/fight, select a hit enemy unit to poison; poisoned units roll D6 in each Command phase (4+ -> D3 mortal wounds)."),
        ("EC", "Beguiling Form"): ("Supported", "-1 to hit when targeting this model (while selected)."),
        ("EC", "Daemonic Speed"): ("Supported", "Fights First (while selected)."),
        ("EC", "Enthralling Hypnosis (Aura)"): ("Supported", "Enemy units within 6\" that Fall Back must pass a Leadership test or remain stationary (while selected)."),
        ("EC", "Duellist's Hubris"): ("Supported", "Fights First when not leading a unit."),
        ("EC", "Lord of Excess"): ("Supported", "Conditional Lone Operative within 3\" of friendly SLAANESH INFANTRY units."),
        ("EC", "LORD OF THE HOST"): ("Supported", "Conditional Infiltrators/Scouts 6\" if attached to friendly EMPEROR'S CHILDREN BATTLELINE at battle formations."),
        ("EC", "Lethal Obsession"): ("Supported", "Same-target shooting requirement tracked; charge reroll applies vs that target until end of turn."),
        ("EC", "No Prey Can Evade"): ("Supported", "Re-roll Advance and Charge rolls."),
        ("EC", "Unholy Speed"): ("Supported", "Re-roll Advance and Charge rolls."),
        ("EC", "Monarch of the Hunt"): ("Supported", "Quarry selection + melee reroll hooks vs quarry."),
        ("DG", "Death Guard Defenders"): ("Supported", "Conditional Lone Operative within 3\" of friendly DEATH GUARD INFANTRY units."),
        ("DG", "Hovering Death"): ("Supported", "Shoot and charge after Falling Back."),
        ("DG", "Blinding Spray"): ("Partial", "Fights First applied without selection/once-per-battle restriction."),
        ("DG", "Shroud of Disease"): ("Supported", "Leading: attached unit can only be targeted by ranged attacks within 18\"."),
        ("DRU", "ARCHON'S RETINUE"): ("Partial", "Scouts 7\" applied without leader/attachment restriction (affects unit)."),
        ("DRU", "Blur of Blades"): ("Supported", "Leading: unit gains Fights First."),
        ("DRU", "Blur of Movement"): ("Supported", "Charge-after-Advance eligibility."),
        ("DRU", "Aethersails"): ("Supported", "Advance: fixed +6\" Move instead of rolling."),
        ("DRU", "Eviscerating Fly-by"): (
            "Supported",
            "Normal/Advance move over: select a moved-over enemy; roll D6 per model (supports FLY bonus and exclusions).",
        ),
        ("DRU", "Cluster Caltrops"): ("Supported", "Re-roll move-over mortal wound dice (one per model with Cluster Caltrops)."),
        ("DRU", "Fog of Dreams (Psychic)"): ("Supported", "Leading: attached unit can only be targeted by ranged attacks within 18\"."),
        ("DRU", "Polychromatic Camouflage"): ("Supported", "Ranged attacks can only target this unit within 18\"."),
        ("DRU", "Shade Weavers"): ("Supported", "Ranged attacks can only target this unit within 18\"."),
        ("GC", "Sudden Assault"): ("Supported", "Leading: unit gains Fights First."),
        ("GC", "Swift and Deadly"): ("Supported", "Charge-after-Advance eligibility."),
        ("LOV", "Brōkhyr Guild Support"): ("Partial", "Lone Operative applied without 3\" Vehicle/Ironkin proximity or attached-unit restriction."),
        ("LOV", "Science Guild Support"): ("Partial", "Lone Operative applied without 3\" Infantry proximity or exclusion of Lone Operative units."),
        ("LOV", "Teleport Crest"): ("Partial", "Deep Strike granted; leading restriction not enforced where applicable."),
        ("NEC", "Adaptive Strategy"): ("Supported", "Shoot and charge after Falling Back."),
        ("NEC", "Ghostwalk Mantle"): ("Supported", "Leading: unit gains Fights First."),
        ("NEC", "Illuminor"): ("Supported", "Conditional Lone Operative within 3\" of friendly NECRONS units."),
        ("NEC", "Protective Disciples"): ("Supported", "Conditional Lone Operative within 3\" of friendly DESTROYER CULT units."),
        ("NEC", "VANGUARD PROTOCOLS"): ("Partial", "Scouts 8\" applied without attached-unit restriction."),
        ("NEC", "Relentless Combatants"): ("Supported", "Re-roll Charge rolls. Charge-after-Fall-Back eligibility."),
        ("NEC", "Shadowloom"): ("Supported", "Stealth."),
        ("NEC", "Gloom Prism (Aura)"): ("Partial", "Feel No Pain vs Psychic (and mortal where listed) applies to bearer only; aura not propagated."),
        ("NEC", "Nullstone Field Generator (Aura)"): ("Partial", "Feel No Pain vs mortal/psychic applies to bearer only; aura not propagated."),
        ("ORK", "Full Throttle"): ("Supported", "Charge-after-Advance and charge-after-Fall-Back eligibility."),
        ("ORK", "Mekboy"): ("Supported", "Conditional Lone Operative within 3\" of friendly ORKS VEHICLE units."),
        ("ORK", "Super Runts"): ("Partial", "Scouts 9\" applied without leading restriction; hit/wound bonus not implemented."),
        ("ORK", "Tellyporta Tech"): ("Partial", "Deep Strike granted without leading restriction."),
        ("ORK", "Drill Boss"): ("Supported", "Leading: +1 to hit for melee attacks in the unit."),
        ("TAU", "Advanced Armour"): ("Supported", "Feel No Pain 4+ against mortal wounds."),
        ("TAU", "Agile Combatant"): ("Supported", "Shoot after Falling Back."),
        ("TAU", "Recon Drone"): ("Supported", "Infiltrators."),
        ("TYR", "Adaptable Predators"): ("Supported", "Shoot and charge after Falling Back."),
        ("TYR", "Bounding Leap"): ("Supported", "Charge-after-Advance eligibility."),
        ("TYR", "Irresistible Force"): ("Supported", "Charge-after-Fall-Back eligibility."),
        ("TYR", "Foul Spores (Aura)"): ("Partial", "Stealth aura within 6\" for non-MONSTER TYRANIDS units; Benefit of Cover aura not implemented."),
        ("TYR", "Unnatural Resilience"): ("Supported", "Feel No Pain 4+ against mortal wounds."),
        ("TS", "Bounding Leaps"): ("Supported", "Shoot after Falling Back."),
        ("TS", "One Head Looks Forward"): ("Supported", "End of Command phase: Leadership test for the model; gain 1CP on pass."),
        ("TS", "Glamour of Tzeentch (Aura, Psychic)"): ("Supported", "Stealth aura within 6\" for THOUSAND SONS INFANTRY units."),
        ("TS", "Servile Pawns"): ("Supported", "Conditional Lone Operative within 3\" of friendly THOUSAND SONS INFANTRY units."),
        ("TS", "Split"): (
            "Supported",
            "Queued after attack resolution: 4+ spawns 2 Blue for destroyed Pink, or 1 Brimstone for destroyed Blue; placement handled.",
        ),
        ("TS", "Sullen Malevolence (Aura)"): (
            "Supported",
            "Enemy units within 6\" suffer Leadership +1 while the unit contains Blue Horrors and Blue abilities are active.",
        ),
        ("TS", "Exploding Horrors"): (
            "Supported",
            "Fight selection: choose engaged enemy and Brimstones; each 4+ destroys a Brimstone and deals 1 mortal.",
        ),
        ("TS", "HORRORS ARE PINK. HORRORS ARE BLUE. WHEREONCE THERE WAS ONE, NOW THERE ARE TWO."): (
            "Supported",
            "When no Pink Horrors remain, unit swaps to Blue Horrors datasheet; Blue abilities are suppressed while Pink models remain.",
        ),
        ("TS", "Illusions of Tzeentch (Psychic)"): ("Supported", "Leading: attached unit can only be targeted by ranged attacks within 18\"."),
        ("WE", "Furious Onslaught"): ("Supported", "Ranged attacks vs closest eligible target within 18\" allow an optional Hit re-roll."),
        ("WE", "Reborn in Blood"): ("Supported", "Revive + reserves placement; restricted to the next Movement phase only."),
        ("WE", "Wrathful Presence"): ("Supported", "Battle-round selection sets one of the three Wrathful Presence abilities."),
        ("WE", "The Blood God's Favour"): ("Supported", "Blessings of Khorne roll can re-roll up to six dice while Angron is on the battlefield."),
        ("WE", "Overwhelming Wrath (Aura)"): ("Supported", "Enemy units within 6\" that Fall Back must pass a Leadership test or remain stationary."),
        ("WE", "Driven by Ultimate Rage (Aura)"): ("Supported", "Friendly WORLD EATERS within 6\" ignore negative Move, Advance/Charge, and melee Hit modifiers."),
        ("WE", "Lord of Murder"): ("Supported", "Conditional Lone Operative within 3\" of friendly WORLD EATERS INFANTRY."),
        ("WE", "Beacons of Rage (Aura)"): ("Supported", "+1 hit (melee) and +1 wound vs Below Half-strength; excludes Monster/Vehicle."),
        ("WE", "Fire Riders"): (
            "Supported",
            "Leading: unit gains Deep Strike and phase-through movement (Normal/Advance/Fall Back/Charge); auto-pass Desperate Escape tests.",
        ),
        ("WE", "Forwards, for Blood!"): ("Supported", "Leading: re-roll Advance rolls and the Blood Surge D6."),
        ("WE", "Bloody Fury"): (
            "Supported",
            "Ranged attacks vs closest enemy unit: re-roll Hit roll. Charges vs closest eligible enemy unit: re-roll Charge roll.",
        ),
        ("WE", "To Slake its Rage"): ("Supported", "Advance-and-charge eligibility."),
        ("WE", "Idol of Blessed Blood"): ("Supported", "Adds an extra Blessings die for each on-battlefield model with this ability."),
        ("WE", "Icon of Khorne"): ("Supported", "Enemy unit destroyed by bearer grants +1 Bloodshed point."),
        ("WE", "Murderlust"): ("Supported", "Advance-and-charge eligibility."),
        ("WE", "Collar of Khorne"): ("Supported", "Feel No Pain 3+ against Psychic attacks."),
        ("WE", "Possessed Lord"): ("Supported", "Once-per-battle Fight phase: +3 Attacks and Devastating Wounds."),
        ("WE", "Lord of the Eightbound"): ("Supported", "Leader gains Deep Strike and Scouts 6\" if attached to WORLD EATERS POSSESSED at battle formations."),
        ("WE", "Rage Embodied (Aura)"): ("Supported", "+1 melee Attacks aura within 6\" for BLOOD LEGIONS."),
        ("WE", "Daemon Lord of Khorne (Aura)"): ("Supported", "+1 to hit in melee aura within 6\" for BLOOD LEGIONS."),
        ("WE", "Blood Surge"): ("Supported", "Opponent Shooting phase: optional D6+2\" move toward closest non-AIRCRAFT enemy; blocked if Battle-shocked/engaged; once per phase."),
        ("WE", "Frenzy"): ("Supported", "After being targeted, Helbrute can shoot or fight vs the attacker (eligible target check)."),
        ("SM", "Shadowmaster"): ("Supported", "Leading: attached unit can only be targeted by ranged attacks within 12\"."),
        ("SM", "Shrouding (Psychic)"): (
            "Partial",
            "Leading: ranged targeting restriction within 12\" supported; Stealth grant not implemented.",
        ),
        ("SM", "Tempormortis"): ("Supported", "Fights First while leading a unit."),
        ("SM", "Pack Leader"): ("Supported", "Unit cannot be your Warlord or be given Enhancements."),
        ("TS", "Master of Magicks (Psychic)"): (
            "Supported",
            "Shooting phase: choose Ignores Cover, Lethal Hits, or Sustained Hits D3 for Bolt of Change until end of phase.",
        ),
        ("DG", "Mischief Makers"): (
            "Supported",
            "Enemy non-TITAN units selected to fight while engaged suffer -1 to hit with melee attacks until end of phase.",
        ),
    }
    out: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for (fid, name), val in raw.items():
        out[(str(fid or "").strip().upper(), _norm(name))] = val
    return out


def _datasheet_ability_support_by_name_faction_datasheet() -> Dict[Tuple[str, str, str], Tuple[str, str]]:
    raw = {
        ("WE", "Frenzy", "000002632"): ("Supported", "After being targeted, Helbrute can shoot or fight vs the attacker (eligible target check)."),
        ("WE", "Furious Onslaught", "000002638"): ("Supported", "Ranged attacks vs closest eligible target within 18\" allow an optional Hit re-roll."),
        ("CD", "Prey of the Blood God", "000001104"): (
            "Supported",
            "BR1 prey selection; melee attacks vs prey can re-roll the Wound roll; re-pick when prey is destroyed.",
        ),
        ("CD", "Prey of the Blood God", "000004102"): (
            "Supported",
            "BR1 prey selection; weapons gain [LETHAL HITS] vs prey; re-pick when prey is destroyed.",
        ),
        ("GC", "Psychic Spoor", "000001569"): (
            "Supported",
            "BR1 prey selection; attacks vs prey can re-roll Hit and Wound rolls (no re-pick on destruction).",
        ),
    }
    out: Dict[Tuple[str, str, str], Tuple[str, str]] = {}
    for (fid, name, dsid), val in raw.items():
        out[(str(fid or "").strip().upper(), _norm(name), str(dsid or "").strip())] = val
    return out


def _datasheet_support_by_name_faction() -> Dict[Tuple[str, str], Tuple[str, str]]:
    """
    Explicit full-datasheet support overrides.
    Use this only when abilities, wargear, points, keywords, damaged profiles,
    and other special sections are all confirmed supported.
    """
    raw: Dict[Tuple[str, str], Tuple[str, str]] = {
        # ("WE", "Angron"): ("Supported", "Full datasheet support verified."),
        ("WE", "Furious Onslaught"): ("Supported", "Ranged attacks vs closest eligible target within 18\" allow an optional Hit re-roll."),
    }
    out: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for (fid, name), val in raw.items():
        out[(str(fid or "").strip().upper(), _norm(name))] = val
    return out

def _seed_ability_support_maps(abilities: List[dict], det_abilities_rows: List[dict]) -> None:
    global ABILITY_SUPPORT_BY_ID, ABILITY_SUPPORT_BY_NAME_FACTION, ABILITY_SUPPORT_BY_NAME_FACTION_DS
    ABILITY_SUPPORT_BY_ID = {}
    ABILITY_SUPPORT_BY_NAME_FACTION = {}
    ABILITY_SUPPORT_BY_NAME_FACTION_DS = {}

    name_to_ids: Dict[str, List[str]] = {}
    for ab in abilities:
        ab_id = str(ab.get("id", "") or "").strip()
        if not ab_id:
            continue
        name_norm = _norm(ab.get("name", "") or "")
        if not name_norm:
            continue
        name_to_ids.setdefault(name_norm, []).append(ab_id)
    for name_norm, val in _ability_id_support_by_name().items():
        for ab_id in name_to_ids.get(name_norm, []):
            ABILITY_SUPPORT_BY_ID[ab_id] = val

    det_name_to_ids: Dict[str, List[str]] = {}
    for row in det_abilities_rows:
        det_id = str(row.get("id", "") or "").strip()
        if not det_id:
            continue
        name_norm = _norm(row.get("name", "") or "")
        if not name_norm:
            continue
        det_name_to_ids.setdefault(name_norm, []).append(det_id)
    for name_norm, val in _detachment_ability_support_by_name().items():
        for det_id in det_name_to_ids.get(name_norm, []):
            ABILITY_SUPPORT_BY_ID[det_id] = val

    restriction_support = _restriction_support_by_name()
    for fid, meta in FACTION_RULE_METADATA.items():
        fid_norm = str(fid or "").strip().upper()
        for restriction in list(meta.get("restrictions", []) or []):
            key = _norm(restriction)
            if key in restriction_support:
                ABILITY_SUPPORT_BY_NAME_FACTION[(fid_norm, key)] = restriction_support[key]

    for name_norm, val in _datasheet_ability_support_global().items():
        for fid in SUPPORTED_FACTION_IDS:
            fid_norm = str(fid or "").strip().upper()
            ABILITY_SUPPORT_BY_NAME_FACTION[(fid_norm, name_norm)] = val

    for key, val in _datasheet_ability_support_by_name_faction().items():
        ABILITY_SUPPORT_BY_NAME_FACTION[key] = val
    for key, val in _datasheet_ability_support_by_name_faction_datasheet().items():
        ABILITY_SUPPORT_BY_NAME_FACTION_DS[key] = val


def _classify_ability_base(
    name: str,
    description: str,
    *,
    ability_id: str = "",
    faction_id: str = "",
    datasheet_id: str = "",
) -> Tuple[str, str]:
    ab_id = str(ability_id or "").strip()
    if ab_id:
        mapped = ABILITY_SUPPORT_BY_ID.get(ab_id)
        if mapped:
            return mapped

    desc_support = _warlord_enhancement_restriction_support(description)
    unique_model_support = _unique_model_restriction_support(description)
    chapter_restriction_support = None
    if description:
        if "RESTRICTIONS" not in description.upper():
            chapter_restriction_support = _space_marine_chapter_restriction_support(description)
    else:
        chapter_restriction_support = _space_marine_chapter_restriction_support(name)
    if desc_support:
        return desc_support
    if unique_model_support:
        return unique_model_support
    if chapter_restriction_support:
        return chapter_restriction_support
    closest_m_veh_support = _closest_monster_vehicle_reroll_support(description)
    monster_vehicle_reroll_support = _monster_vehicle_reroll_support(description)
    unit_contains_oc_support = _unit_contains_oc_support(description)
    aura_oc_support = _aura_objective_control_support(description)
    aura_adv_charge_support = _aura_advance_charge_roll_support(description)
    aura_hit_support = _aura_hit_bonus_support(description)
    aura_strength_support = _aura_strength_support(description)
    aura_toughness_support = _aura_toughness_support(description)
    aura_melee_ap_support = _aura_melee_ap_support(description)
    fall_back_shoot_support = _fall_back_shoot_support(description)
    advance_no_roll_support = _advance_no_roll_fixed_distance_support(description)
    movement_ignore_vertical_support = _movement_ignore_vertical_distance_support(description)
    charge_move_devastating_support = _charge_move_devastating_wounds_support(description)
    defensive_charge_roll_penalty_support = _defensive_charge_roll_penalty_support(description)
    phase_move_support = _leading_unit_phase_move_support(description)
    phase_terrain_support = _leading_unit_move_and_phase_terrain_support(description)
    move_over_friendly_support = _move_over_friendly_monster_vehicle_support(description)
    move_over_low_terrain_support = _move_over_low_terrain_support(description)
    titanic_move_through_support = _titanic_move_through_support(description)
    move_over_mortal_support = _move_over_mortal_wounds_support(description)
    common_support = _bearer_unit_common_support(description)
    leading_support = _leading_unit_common_support(description)
    bearer_invuln_support = _bearer_invulnerable_save_support(description)
    bearer_save_support = _bearer_save_characteristic_support(description)
    model_fnp_support = _model_fnp_support(description)
    attached_character_fnp_support = _attached_character_fnp_support(description)
    unit_contains_character_fnp_support = _unit_contains_character_fnp_support(description)
    leading_unit_contains_invuln_support = _leading_unit_contains_invuln_support(description)
    bearer_smoke_support = _bearer_smoke_keyword_support(description)
    bearer_unit_keyword_support = _bearer_unit_keyword_support(description)
    unit_hit_reroll_support = _unit_hit_reroll_ones_support(description)
    unit_wound_reroll_support = _unit_wound_reroll_ones_support(description)
    target_hit_penalty_support = _target_hit_roll_penalty_support(description)
    defensive_wound_penalty_support = _defensive_wound_penalty_support(description)
    strength_gt_toughness_wound_penalty_support = _defensive_strength_gt_toughness_wound_penalty_support(description)
    melee_damage_support = _melee_damage_bonus_support(description)
    melee_charge_strength_damage_support = _melee_charge_strength_damage_support(description)
    two_melee_weapons_support = _two_melee_weapons_bonus_support(description)
    attached_possessed_support = _attached_possessed_formation_bonus_support(description)
    attached_battleline_infiltrators_support = _attached_battleline_infiltrators_scouts_support(description)
    transport_support = _transport_disembark_support(description)
    transport_reactive_disembark_support = _transport_reactive_disembark_support(description)
    end_of_fight_embark_support = _end_of_fight_embark_support(description)
    enemy_move_reactive_d6_support = _enemy_move_reactive_d6_support(description)
    horde_move_support = _horde_move_support(description)
    setup_reactive_shoot_charge_support = _setup_reactive_shoot_or_charge_support(description)
    sticky_support = _sticky_objective_support(description)
    bodyguard_return_support = _command_phase_bodyguard_return_support(description)
    charge_phase_bodyguard_loss_support = _charge_phase_bodyguard_loss_support(description)
    opponent_turn_reserves_support = _opponent_turn_strategic_reserves_support(description)
    strategic_reserves_early_arrival_support = _strategic_reserves_early_arrival_support(description)
    opponent_turn_destroyed_reposition_support = _opponent_turn_destroyed_reposition_support(description)
    enemy_fall_back_desperate_escape_support = _enemy_fall_back_desperate_escape_support(description)
    command_phase_bonus_cp_support = _command_phase_bonus_cp_support(description)
    phase_end_leadership_cp_gain_support = _phase_end_leadership_cp_gain_support(description)
    command_phase_regain_wound_support = _command_phase_regain_wound_support(description)
    start_shooting_phase_visible_battleshock_support = _start_shooting_phase_visible_battleshock_support(description)
    post_shoot_battleshock_support = _post_shoot_battleshock_support(description)
    post_shoot_shoot_again_support = _post_shoot_shoot_again_support(description)
    post_shoot_infantry_mortal_support = _post_shoot_infantry_mortal_wounds_battleshock_support(description)
    post_shoot_wracking_agonies_support = _post_shoot_wracking_agonies_support(description)
    post_shoot_suppression_support = _post_shoot_suppression_support(description)
    post_shoot_no_cover_support = _post_shoot_no_cover_support(description)
    post_shoot_snare_support = _post_shoot_snare_support(description)
    post_shoot_leadership_debuff_support = _post_shoot_leadership_debuff_support(description)
    aura_battleshock_leadership_penalty_support = _aura_battleshock_leadership_penalty_support(description)
    fight_phase_engagement_battleshock_support = _fight_phase_engagement_battleshock_support(description)
    fight_phase_aura_battleshock_support = _fight_phase_aura_battleshock_support(description)
    charge_end_engagement_battleshock_support = _charge_end_engagement_battleshock_support(description)
    start_any_phase_battleshock_clear_support = _start_any_phase_battleshock_clear_support(description)
    fight_phase_below_starting_strength_fight_first_support = _fight_phase_below_starting_strength_fight_first_support(description)
    fight_phase_end_mortal_support = _fight_phase_end_mortal_wounds_support(description)
    fight_phase_melee_ap_boost_support = _fight_phase_once_melee_attacks_ap_support(description)
    start_any_phase_damage_set_one_support = _start_any_phase_damage_set_one_support(description)
    start_any_phase_unit_fnp_support = _start_any_phase_unit_fnp_support(description)
    dark_ritual_support = _dark_ritual_support(description)
    movement_phase_normal_move_weapon_attacks_bonus_support = _movement_phase_once_normal_move_weapon_attacks_bonus_support(description)
    movement_phase_speed_mortal_support = _movement_phase_normal_move_speed_mortal_wounds_support(description)
    movement_phase_end_mortal_table_support = _movement_phase_end_enemy_within_range_mortal_table_support(description)
    movement_phase_end_mortal_threshold_support = _movement_phase_end_enemy_within_range_mortal_threshold_support(description)
    movement_phase_visible_wound_bonus_support = _movement_phase_end_visible_wound_bonus_support(description)
    movement_phase_visible_hit_bonus_support = _movement_phase_end_visible_hit_bonus_support(description)
    grenade_pack_flyover_support = _grenade_pack_flyover_support(description)
    battle_focus_token_refund_support = _battle_focus_agile_maneuver_token_refund_support(description)
    leading_leadership_reroll_support = _leading_leadership_reroll_support(description)
    dark_pacts_leadership_reroll_support = _dark_pacts_leadership_reroll_support(description)
    start_of_battle_keyword_reroll_support = _start_of_battle_keyword_reroll_ones_support(description)
    daemonic_patrons_support = _daemonic_patrons_support(description)
    return_on_death_support = _return_on_death_support(description)
    crewed_platform_support = _crewed_platform_support(description)
    melee_fight_on_death_support = _melee_fight_on_death_after_attacks_support(description)
    conditional_lone_operative_support = _conditional_lone_operative_support(description)
    charge_target_strength_bonus_support = _charge_target_strength_bonus_support(description)
    daemonic_allegiance_support = _daemonic_allegiance_wargear_support(description)
    reinforcements_denial_support = _reinforcements_denial_support(description)
    cp_on_destroy_support = _gain_cp_on_destroy_support(description)
    battlesuit_support_system_support = _battlesuit_support_system_support(name, description)
    attack_roll_rule_support = _attack_roll_rule_support(description)
    objective_attack_keyword_support = _objective_attack_keyword_support(description)
    half_range_attack_keyword_support = _half_range_attack_keyword_support(description)
    target_keyword_attack_keyword_support = _target_keyword_attack_keyword_support(description)
    weapon_keyword_grant_support = _weapon_keyword_grant_support(description)
    closest_enemy_hit_charge_support = _closest_enemy_hit_and_charge_reroll_support(description)
    orders_support = _orders_section_support(name, description)
    attached_unit_support = _attached_unit_support(name, description)
    model_reroll_support = _model_reroll_wound_vs_character_support(description)
    selected_to_shoot_or_fight_reroll_choice_support = _selected_to_shoot_or_fight_reroll_choice_support(description)
    selected_to_shoot_reroll_support = _selected_to_shoot_single_reroll_support(description)
    attack_roll_cp_support = _attack_roll_plus_cp_on_destroy_support(description)
    attack_roll_battleshock_support = _attack_roll_plus_on_kill_battleshock_support(description)
    on_kill_battleshock_support = _on_kill_battleshock_support(description)
    model_hit_vs_fly_support = _model_hit_bonus_vs_fly_support(description)
    model_target_strength_support = _model_target_strength_hit_wound_support(description)
    model_self_strength_support = _model_self_strength_hit_wound_support(description)
    model_attack_roll_bonus_support = _model_attack_roll_bonus_support(description)
    targeted_stratagem_discount_support = _targeted_stratagem_cp_discount_support(description)
    targeted_stratagem_increase_support = _targeted_stratagem_cp_increase_support(description)
    brutal_example_overwatch_support = _brutal_example_overwatch_support(description)
    charge_end_mortal_support = _charge_end_mortal_wounds_support(description)
    fight_within_3_support = _fight_within_3_support(description)
    allocated_damage_reduction_support = _allocated_damage_reduction_support(description)
    ranged_ignore_bs_hit_support = _ranged_ignore_bs_hit_modifiers_support(description)
    ranged_targeting_restriction_support = _ranged_targeting_restriction_support(description)

    if battlesuit_support_system_support:
        return battlesuit_support_system_support
    if conditional_lone_operative_support:
        return conditional_lone_operative_support
    if move_over_friendly_support:
        return move_over_friendly_support
    if move_over_low_terrain_support:
        return move_over_low_terrain_support
    if titanic_move_through_support:
        return titanic_move_through_support
    if move_over_mortal_support:
        return move_over_mortal_support
    if ranged_ignore_bs_hit_support:
        return ranged_ignore_bs_hit_support
    if ranged_targeting_restriction_support:
        return ranged_targeting_restriction_support
    if fight_phase_below_starting_strength_fight_first_support:
        return fight_phase_below_starting_strength_fight_first_support
    prey_selection_support = _prey_selection_support(description)
    if prey_selection_support:
        return prey_selection_support

    fid = str(faction_id or "").strip().upper()
    name_norm = _norm(name)
    dsid = str(datasheet_id or "").strip()
    ambiguous_name = False
    if name_norm and dsid:
        key = (fid, name_norm, dsid)
        if key in ABILITY_SUPPORT_BY_NAME_FACTION_DS:
            return ABILITY_SUPPORT_BY_NAME_FACTION_DS[key]
        for k_fid, k_name, _k_ds in ABILITY_SUPPORT_BY_NAME_FACTION_DS.keys():
            if k_fid == fid and k_name == name_norm:
                ambiguous_name = True
                break
    if name_norm and (not ambiguous_name) and (fid, name_norm) in ABILITY_SUPPORT_BY_NAME_FACTION:
        return ABILITY_SUPPORT_BY_NAME_FACTION[(fid, name_norm)]
    if fid == "DRU" and "(pain)" in str(name or "").lower():
        return ("Supported", "Power from Pain ability effects implemented.")
    if closest_m_veh_support:
        return closest_m_veh_support
    if monster_vehicle_reroll_support:
        return monster_vehicle_reroll_support
    if unit_contains_oc_support:
        return unit_contains_oc_support
    if aura_oc_support:
        return aura_oc_support
    if aura_adv_charge_support:
        return aura_adv_charge_support
    if aura_hit_support:
        return aura_hit_support
    if aura_strength_support:
        return aura_strength_support
    if aura_toughness_support:
        return aura_toughness_support
    if aura_melee_ap_support:
        return aura_melee_ap_support
    if fall_back_shoot_support:
        return fall_back_shoot_support
    if advance_no_roll_support:
        return advance_no_roll_support
    if movement_ignore_vertical_support:
        return movement_ignore_vertical_support
    if charge_move_devastating_support:
        return charge_move_devastating_support
    if defensive_charge_roll_penalty_support:
        return defensive_charge_roll_penalty_support
    if phase_move_support:
        return phase_move_support
    if phase_terrain_support:
        return phase_terrain_support
    if half_range_attack_keyword_support:
        return half_range_attack_keyword_support
    if target_keyword_attack_keyword_support:
        return target_keyword_attack_keyword_support
    if unit_contains_character_fnp_support:
        return unit_contains_character_fnp_support
    if leading_unit_contains_invuln_support:
        return leading_unit_contains_invuln_support
    if common_support and leading_support:
        if common_support[0] == "Supported" and leading_support[0] == "Supported":
            notes = " ".join([common_support[1], leading_support[1]]).strip()
            return ("Supported", notes)
        return common_support
    if common_support:
        return common_support
    if leading_support:
        return leading_support
    if attached_character_fnp_support:
        return attached_character_fnp_support
    if weapon_keyword_grant_support:
        return weapon_keyword_grant_support
    if bearer_invuln_support:
        return bearer_invuln_support
    if bearer_save_support:
        return bearer_save_support
    if model_fnp_support:
        return model_fnp_support
    if bearer_smoke_support:
        return bearer_smoke_support
    if bearer_unit_keyword_support:
        return bearer_unit_keyword_support
    if unit_hit_reroll_support:
        return unit_hit_reroll_support
    if unit_wound_reroll_support:
        return unit_wound_reroll_support
    if target_hit_penalty_support:
        return target_hit_penalty_support
    if defensive_wound_penalty_support:
        return defensive_wound_penalty_support
    if strength_gt_toughness_wound_penalty_support:
        return strength_gt_toughness_wound_penalty_support
    if melee_damage_support:
        return melee_damage_support
    if melee_charge_strength_damage_support:
        return melee_charge_strength_damage_support
    if two_melee_weapons_support:
        return two_melee_weapons_support
    if attached_possessed_support:
        return attached_possessed_support
    if attached_battleline_infiltrators_support:
        return attached_battleline_infiltrators_support
    if end_of_fight_embark_support:
        return end_of_fight_embark_support
    if transport_support:
        return transport_support
    if transport_reactive_disembark_support:
        return transport_reactive_disembark_support
    if enemy_move_reactive_d6_support:
        return enemy_move_reactive_d6_support
    if horde_move_support:
        return horde_move_support
    if setup_reactive_shoot_charge_support:
        return setup_reactive_shoot_charge_support
    if sticky_support:
        return sticky_support
    if bodyguard_return_support:
        return bodyguard_return_support
    if charge_phase_bodyguard_loss_support:
        return charge_phase_bodyguard_loss_support
    if opponent_turn_reserves_support:
        return opponent_turn_reserves_support
    if strategic_reserves_early_arrival_support:
        return strategic_reserves_early_arrival_support
    if opponent_turn_destroyed_reposition_support:
        return opponent_turn_destroyed_reposition_support
    if enemy_fall_back_desperate_escape_support:
        return enemy_fall_back_desperate_escape_support
    if command_phase_bonus_cp_support:
        return command_phase_bonus_cp_support
    if phase_end_leadership_cp_gain_support:
        return phase_end_leadership_cp_gain_support
    if command_phase_regain_wound_support:
        return command_phase_regain_wound_support
    if start_shooting_phase_visible_battleshock_support:
        return start_shooting_phase_visible_battleshock_support
    if post_shoot_battleshock_support:
        return post_shoot_battleshock_support
    if post_shoot_shoot_again_support:
        return post_shoot_shoot_again_support
    if post_shoot_infantry_mortal_support:
        return post_shoot_infantry_mortal_support
    if post_shoot_wracking_agonies_support:
        return post_shoot_wracking_agonies_support
    if post_shoot_suppression_support:
        return post_shoot_suppression_support
    if post_shoot_no_cover_support:
        return post_shoot_no_cover_support
    if post_shoot_snare_support:
        return post_shoot_snare_support
    if post_shoot_leadership_debuff_support:
        return post_shoot_leadership_debuff_support
    if aura_battleshock_leadership_penalty_support:
        return aura_battleshock_leadership_penalty_support
    if fight_phase_engagement_battleshock_support:
        return fight_phase_engagement_battleshock_support
    if fight_phase_aura_battleshock_support:
        return fight_phase_aura_battleshock_support
    if charge_end_engagement_battleshock_support:
        return charge_end_engagement_battleshock_support
    if start_any_phase_battleshock_clear_support:
        return start_any_phase_battleshock_clear_support
    if fight_phase_end_mortal_support:
        return fight_phase_end_mortal_support
    if fight_phase_melee_ap_boost_support:
        return fight_phase_melee_ap_boost_support
    if start_any_phase_damage_set_one_support:
        return start_any_phase_damage_set_one_support
    if start_any_phase_unit_fnp_support:
        return start_any_phase_unit_fnp_support
    if dark_ritual_support:
        return dark_ritual_support
    if movement_phase_normal_move_weapon_attacks_bonus_support:
        return movement_phase_normal_move_weapon_attacks_bonus_support
    if movement_phase_speed_mortal_support:
        return movement_phase_speed_mortal_support
    if movement_phase_end_mortal_table_support:
        return movement_phase_end_mortal_table_support
    if movement_phase_end_mortal_threshold_support:
        return movement_phase_end_mortal_threshold_support
    if grenade_pack_flyover_support:
        return grenade_pack_flyover_support
    if movement_phase_visible_wound_bonus_support:
        return movement_phase_visible_wound_bonus_support
    if movement_phase_visible_hit_bonus_support:
        return movement_phase_visible_hit_bonus_support
    if battle_focus_token_refund_support:
        return battle_focus_token_refund_support
    if leading_leadership_reroll_support:
        return leading_leadership_reroll_support
    if dark_pacts_leadership_reroll_support:
        return dark_pacts_leadership_reroll_support
    if start_of_battle_keyword_reroll_support:
        return start_of_battle_keyword_reroll_support
    if daemonic_patrons_support:
        return daemonic_patrons_support
    if melee_fight_on_death_support:
        return melee_fight_on_death_support
    if return_on_death_support:
        return return_on_death_support
    if crewed_platform_support:
        return crewed_platform_support
    if charge_target_strength_bonus_support:
        return charge_target_strength_bonus_support
    if daemonic_allegiance_support:
        return daemonic_allegiance_support
    if reinforcements_denial_support:
        return reinforcements_denial_support
    if cp_on_destroy_support:
        return cp_on_destroy_support
    if attack_roll_rule_support:
        return attack_roll_rule_support
    if objective_attack_keyword_support:
        return objective_attack_keyword_support
    if closest_enemy_hit_charge_support:
        return closest_enemy_hit_charge_support
    if orders_support:
        return orders_support
    if attached_unit_support:
        return attached_unit_support
    if model_reroll_support:
        return model_reroll_support
    if selected_to_shoot_or_fight_reroll_choice_support:
        return selected_to_shoot_or_fight_reroll_choice_support
    if selected_to_shoot_reroll_support:
        return selected_to_shoot_reroll_support
    if attack_roll_cp_support:
        return attack_roll_cp_support
    if attack_roll_battleshock_support:
        return attack_roll_battleshock_support
    if on_kill_battleshock_support:
        return on_kill_battleshock_support
    if model_hit_vs_fly_support:
        return model_hit_vs_fly_support
    if model_target_strength_support:
        return model_target_strength_support
    if model_self_strength_support:
        return model_self_strength_support
    if model_attack_roll_bonus_support:
        return model_attack_roll_bonus_support
    if targeted_stratagem_discount_support:
        return targeted_stratagem_discount_support
    if targeted_stratagem_increase_support:
        return targeted_stratagem_increase_support
    if brutal_example_overwatch_support:
        return brutal_example_overwatch_support
    if charge_end_mortal_support:
        return charge_end_mortal_support
    if fight_within_3_support:
        return fight_within_3_support
    if allocated_damage_reduction_support:
        return allocated_damage_reduction_support
    return ("Not implemented", "")


def _classify_ability(
    name: str,
    description: str,
    *,
    ability_id: str = "",
    faction_id: str = "",
    datasheet_id: str = "",
) -> Tuple[str, str]:
    status, notes = _classify_ability_base(
        name,
        description,
        ability_id=ability_id,
        faction_id=faction_id,
        datasheet_id=datasheet_id,
    )
    ab_id = str(ability_id or "").strip()
    if ab_id and ab_id in DETACHMENT_ABILITY_IDS:
        status, notes = _enforce_detachment_full_consumption(
            status,
            notes,
            name=name,
            description=description,
        )
    return status, notes


def _warlord_enhancement_restriction_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    warlord_clause = r"(?:this|that|the)?\s*(?:unit|model|models|bearer)?\s*(?:cannot be your|none of these models can be your)\s+warlord"
    enh_clause = r"(?:this|that|the)?\s*(?:unit|model|models|bearer)?\s*(?:cannot\s+)?be given (?:an?\s+)?enhancements?"
    pattern = rf"(?:{warlord_clause}(?:\s+(?:and|or)\s+{enh_clause})?|{enh_clause}(?:\s+(?:and|or)\s+{warlord_clause})?)"
    if not re.fullmatch(pattern, norm):
        return None
    has_warlord = "warlord" in norm
    has_enh = "enhancement" in norm
    if has_warlord and has_enh:
        return ("Supported", "Unit cannot be your Warlord or be given Enhancements.")
    if has_warlord:
        return ("Supported", "Unit cannot be your Warlord.")
    return ("Supported", "Unit cannot be given Enhancements.")


def _space_marine_chapter_restriction_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"your army can include .+ units? but it cannot include (?:any )?adeptus astartes units drawn from any other chapter"
    )
    if re.fullmatch(pattern, norm):
        return ("Supported", "Space Marine chapter restriction enforced during army validation.")
    return None


def _unique_model_restriction_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = r"(?:unless otherwise stated )?you cannot include more than one of this (?:model|unit) in your army"
    if not re.fullmatch(pattern, norm):
        return None
    return ("Supported", "Army validation enforces unique inclusion for this model.")


def _bearer_unit_common_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    text = _strip_html(description)
    text = text.replace("\u2019", "'").replace("\u0192?T", "'")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    # Let the specialized attached-character FNP handler own this exact pattern.
    if re.fullmatch(
        r"while this model is leading a unit other character models attached to "
        r"(?:that unit|the bearers unit|this unit) have (?:the )?feel no pain [1-6](?: ability)?",
        _norm_rules_text(text),
    ):
        return None
    low = text.lower()
    notes: List[str] = []
    leading_prefix = ""
    if re.search(r"while (?:this model|the bearer) is leading a unit", low, flags=re.IGNORECASE):
        leading_prefix = "Leading: "
        if "bearer's unit" not in low:
            low = re.sub(r"\bthat unit\b", "the bearer's unit", low)

    target_pattern = r"(the\s+bearer'?s\s+unit|this\s+unit|this\s+model'?s\s+unit)"

    def _target_label(target: str) -> str:
        target_lower = str(target or "").lower()
        if "bearer" in target_lower:
            return "bearer's unit"
        if "this model" in target_lower:
            return "this model's unit"
        if "this unit" in target_lower:
            return "this unit"
        return "the unit"

    m = re.search(
        rf"add\s+(\d+)\s+to\s+charge\s+rolls?\s+made\s+for\s+{target_pattern}",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        label = _target_label(m.group(2))
        if leading_prefix:
            notes.append(f"{leading_prefix}Charge rolls for the unit get +{m.group(1)}.")
        else:
            notes.append(f"Charge rolls for {label} get +{m.group(1)}.")

    m = re.search(
        rf"add\s+(\d+)\s+to\s+advance\s+and\s+charge\s+rolls?\s+made\s+for\s+{target_pattern}",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        label = _target_label(m.group(2))
        if leading_prefix:
            notes.append(f"{leading_prefix}Advance and Charge rolls for the unit +{m.group(1)}.")
        else:
            notes.append(f"Advance and Charge rolls for {label} +{m.group(1)}.")
    else:
        m = re.search(
            rf"add\s+(\d+)\s+to\s+advance\s+rolls?\s+made\s+for\s+{target_pattern}",
            low,
            flags=re.IGNORECASE,
        )
        if m:
            label = _target_label(m.group(2))
            if leading_prefix:
                notes.append(f"{leading_prefix}Advance rolls for the unit +{m.group(1)}.")
            else:
                notes.append(f"Advance rolls for {label} +{m.group(1)}.")

    advance_charge_re = re.search(r"re-?roll\s+advance\s+and\s+charge\s+rolls?", low, flags=re.IGNORECASE)
    if advance_charge_re:
        if "bearer's unit" in low or "that unit" in low:
            notes.append("Re-roll Advance and Charge rolls for bearer's unit.")
        elif leading_prefix:
            notes.append("Leading: re-roll Advance and Charge rolls for the unit.")
        else:
            notes.append("Re-roll Advance and Charge rolls.")
    advance_only_re = re.search(
        r"re-?roll\s+advance\s+rolls?\s+made\s+for\s+(?:the\s+)?(?:bearer'?s|that)\s+unit",
        low,
        flags=re.IGNORECASE,
    )
    if advance_only_re:
        if leading_prefix:
            notes.append("Leading: re-roll Advance rolls for the unit.")
        else:
            notes.append("Re-roll Advance rolls for bearer's unit.")
    agile_re = re.search(
        r"re-?roll any rolls made for (?:the )?(?:bearer'?s|that) unit while it is performing an agile (?:manoeuvre|maneuver)",
        low,
        flags=re.IGNORECASE,
    )
    if agile_re:
        if leading_prefix:
            notes.append("Leading: re-roll any rolls made for the unit while performing an Agile Manoeuvre.")
        else:
            notes.append("Bearer's unit can re-roll any rolls while performing an Agile Manoeuvre.")

    charge_objective_re = re.search(
        r"bearer'?s\s+unit\s+declares\s+a\s+charge.*?objective\s+marker.*?re-?roll\s+the\s+charge\s+roll",
        low,
        flags=re.IGNORECASE,
    )
    charge_setup_re = re.search(
        r"re-?roll\s+charge\s+rolls?.*?\bset\s+up\s+on\s+the\s+battlefield\b",
        low,
        flags=re.IGNORECASE,
    )
    if charge_objective_re:
        if leading_prefix:
            notes.append("Leading: charge reroll if target is within objective range.")
        else:
            notes.append("Charge reroll if target is within objective range.")
    elif charge_setup_re:
        if leading_prefix:
            notes.append("Leading: charge reroll on setup turns.")
        else:
            notes.append("Charge reroll on setup turns.")
    elif not advance_charge_re and re.search(r"re-?roll\s+charge\s+rolls?", low, flags=re.IGNORECASE):
        if re.search(r"bearer'?s\s+unit", low, flags=re.IGNORECASE):
            notes.append("Re-roll Charge rolls for bearer's unit.")
        elif leading_prefix:
            notes.append("Leading: re-roll Charge rolls for the unit.")
        else:
            notes.append("Re-roll Charge rolls.")

    eligible_charge = (
        "eligible to declare a charge" in low
        or "eligible to charge" in low
        or "eligible to shoot and declare a charge" in low
        or "eligible to shoot and charge" in low
    )
    if eligible_charge:
        has_advance = ("advance" in low) or ("advanced" in low) or ("advancing" in low)
        has_fall_back = ("fell back" in low) or ("fall back" in low) or ("falling back" in low)
        if has_advance and has_fall_back:
            notes.append("Charge-after-Advance/Fall Back eligibility.")
        elif has_advance:
            notes.append("Charge-after-Advance eligibility.")
        elif has_fall_back:
            notes.append("Charge-after-Fall-Back eligibility.")

    m = re.search(
        r"models\s+in\s+the\s+bearer'?s\s+unit\s+have\s+a\s+leadership\s+characteristic\s+of\s+(\d+)\+?",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        notes.append(f"Bearer's unit Leadership set to {m.group(1)}+.")

    m = re.search(
        r"models\s+in\s+(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit)\s+have\s+a\s+move\s+characteristic\s+of\s+(\d+)",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        match_text = m.group(0)
        if leading_prefix:
            notes.append(f"{leading_prefix}Move set to {m.group(1)}\".")
        elif "bearer" in match_text:
            notes.append(f"Bearer's unit Move set to {m.group(1)}\".")
        else:
            notes.append(f"Unit Move set to {m.group(1)}\".")

    m = re.search(
        r"add\s+(\d+)\s*\"?\s+to\s+the\s+move\s+characteristic\s+of\s+models\s+in\s+"
        r"(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit)",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        match_text = m.group(0)
        if leading_prefix:
            notes.append(f"{leading_prefix}Move characteristic +{m.group(1)}\".")
        elif "bearer" in match_text:
            notes.append(f"Bearer's unit Move characteristic +{m.group(1)}\".")
        else:
            notes.append(f"Unit Move characteristic +{m.group(1)}\".")

    m = re.search(
        r"add\s+(\d+)\s+to\s+the\s+objective\s+control\s+characteristic\s+of\s+(?:models\s+in\s+)?"
        r"the\s+bearer'?s\s+unit",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        if leading_prefix:
            notes.append(f"{leading_prefix}Objective Control for the unit +{m.group(1)}.")
        else:
            notes.append(f"Bearer's unit Objective Control +{m.group(1)}.")
    elif leading_prefix:
        m = re.search(
            r"add\s+(\d+)\s+to\s+the\s+objective\s+control\s+characteristic\s+of\s+(?:models\s+in\s+)?"
            r"that\s+unit",
            low,
            flags=re.IGNORECASE,
        )
        if m:
            notes.append(f"{leading_prefix}Objective Control for the unit +{m.group(1)}.")

    m = re.search(
        r"(?:models?\s+in\s+)?(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit)\s+"
        r"(?:have|has)\s+(?:a\s+|the\s+)?feel\s+no\s+pain\s*([1-6])\+?(?:\s+ability)?",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        match_text = m.group(0)
        if leading_prefix:
            notes.append(f"{leading_prefix}Feel No Pain {m.group(1)}+.")
        elif "bearer" in match_text:
            notes.append(f"Bearer's unit gains Feel No Pain {m.group(1)}+.")
        else:
            notes.append(f"Unit gains Feel No Pain {m.group(1)}+.")

    m = re.search(
        r"(?:models?\s+in\s+)?(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit)\s+"
        r"(?:have|has)\s+(?:a\s+|the\s+)?([1-6])\+?\s+invulnerable\s+save",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        match_text = m.group(0)
        if leading_prefix:
            notes.append(f"{leading_prefix}Invulnerable save {m.group(1)}+.")
        elif "bearer" in match_text:
            notes.append(f"Bearer's unit gains a {m.group(1)}+ invulnerable save.")
        else:
            notes.append(f"Unit gains a {m.group(1)}+ invulnerable save.")

    m = re.search(
        r"(?:(melee|ranged)\s+)?weapons?\s+equipped\s+by\s+models\s+in\s+(?:the\s+bearer'?s\s+unit|that\s+unit).*?"
        r"sustained\s+hits\s*(\d+)",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        scope = (m.group(1) or "").strip().lower()
        val = m.group(2)
        if scope:
            if leading_prefix:
                notes.append(f"{leading_prefix}{scope} weapons gain Sustained Hits {val}.")
            else:
                notes.append(f"Bearer's unit {scope} weapons gain Sustained Hits {val}.")
        else:
            if leading_prefix:
                notes.append(f"{leading_prefix}weapons gain Sustained Hits {val}.")
            else:
                notes.append(f"Bearer's unit weapons gain Sustained Hits {val}.")

    m = re.search(
        r"add\s+(\d+)\s*\"?\s+to\s+the\s+range\s+characteristic\s+of\s+melta\s+weapons?\s+equipped\s+by\s+models\s+in\s+"
        r"(?:the\s+bearer'?s|that|this)\s+unit",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        if leading_prefix:
            notes.append(f"{leading_prefix}Melta weapon range +{m.group(1)}\".")
        else:
            notes.append(f"Bearer's unit Melta weapon range +{m.group(1)}\".")

    m = re.search(
        r"(?:(melee|ranged)\s+)?(?:weapons?\s+equipped\s+by\s+models\s+in|attacks?\s+made\s+by\s+models\s+in)\s+"
        r"(?:the\s+bearer'?s\s+unit|that\s+unit).*?ignores\s+cover",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        scope = (m.group(1) or "").strip().lower()
        uses_attacks = bool(re.search(r"attacks?\s+made\s+by\s+models\s+in", low, flags=re.IGNORECASE))
        subject = "attacks" if uses_attacks else "weapons"
        if scope:
            phrase = f"{scope} {subject} ignore cover."
        else:
            phrase = f"{subject.capitalize()} ignore cover."
        if leading_prefix:
            notes.append(f"{leading_prefix}{phrase}")
        else:
            notes.append(f"Bearer's unit {phrase[0].lower() + phrase[1:]}")

    m = re.search(
        r"each\s+time\s+(?:a|an)\s+(?:(melee|ranged)\s+)?attack\s+targets\s+(?:the\s+bearer'?s\s+unit|that\s+unit),\s*"
        r"subtract\s+1\s+from\s+the\s+hit\s+roll",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        scope = (m.group(1) or "").strip().lower()
        scope_text = scope if scope in ("melee", "ranged") else "all"
        effect = f"-1 to hit vs {scope_text} attacks that target the unit."
        if leading_prefix:
            notes.append(f"{leading_prefix}{effect}")
        else:
            notes.append(f"Bearer's unit: {effect}")

    m = re.search(
        r"(?:while|if)\s+(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit)\s+is\s+within\s+range\s+of\s+"
        r"(?:an|one\s+or\s+more)\s+objective\s+marker(?:s)?(?:\s+you\s+control)?\s*,?\s*each\s+time\s+"
        r"(?:a|an)\s+(?:(melee|ranged)\s+)?attack\s+targets\s+"
        r"(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit),\s*models\s+in\s+"
        r"(?:it|that\s+unit|this\s+unit|the\s+bearer'?s\s+unit)\s+(?:have|gain)\s+the\s+benefit\s+of\s+cover",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        scope = (m.group(1) or "").strip().lower()
        scope_text = scope if scope in ("melee", "ranged") else "ranged"
        controlled = "you control" in m.group(0)
        cond = "while within range of an objective marker you control" if controlled else "while within range of an objective marker"
        effect = f"Benefit of Cover vs {scope_text} attacks that target the unit."
        if leading_prefix:
            notes.append(f"{leading_prefix}{cond}: {effect}")
        else:
            notes.append(f"Bearer's unit: {cond}; {effect}")

    m = re.search(
        r"each\s+time\s+(?:a|an)\s+(?:(melee|ranged)\s+)?attack\s+targets\s+"
        r"(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit),\s*models\s+in\s+"
        r"(?:it|that\s+unit|this\s+unit|the\s+bearer'?s\s+unit)\s+(?:have|gain)\s+the\s+benefit\s+of\s+cover",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        scope = (m.group(1) or "").strip().lower()
        scope_text = scope if scope in ("melee", "ranged") else "ranged"
        effect = f"Benefit of Cover vs {scope_text} attacks that target the unit."
        if leading_prefix:
            notes.append(f"{leading_prefix}{effect}")
        else:
            notes.append(f"Bearer's unit: {effect}")
    normalized_sentences = []
    for sentence in re.split(r"[.;]\s*", _strip_html(description)):
        norm_sentence = _norm_rules_text(sentence)
        if norm_sentence:
            normalized_sentences.append(norm_sentence)

    lead_prefix = r"(?:while this model is leading a unit )?"
    unit_ref = r"(?:the )?(?:bearers|that|this) unit"
    patterns = [
        rf"{lead_prefix}add \d+ to charge rolls made for {unit_ref}",
        rf"{lead_prefix}add \d+ to advance and charge rolls made for {unit_ref}",
        rf"{lead_prefix}add \d+ to the move characteristic of models in {unit_ref}",
        rf"{lead_prefix}add \d+ to the move characteristic of models in {unit_ref} and add \d+ to advance and charge rolls made for {unit_ref}",
        rf"{lead_prefix}add \d+ to advance rolls made for {unit_ref}",
        rf"{lead_prefix}(?:you can |can )?reroll advance and charge rolls made for (?:this model|{unit_ref})",
        rf"{lead_prefix}(?:you can |can )?reroll charge rolls made for (?:this model|{unit_ref})",
        rf"{lead_prefix}bearers unit declares a charge .* objective marker .* reroll the charge roll",
        rf"{lead_prefix}reroll charge rolls .* set up on the battlefield",
        rf"{lead_prefix}models in {unit_ref} have a leadership characteristic of \d+",
        rf"{lead_prefix}models in {unit_ref} have a move characteristic of \d+",
        rf"{lead_prefix}add \d+ to the objective control characteristic of (?:models in )?{unit_ref}",
        rf"{lead_prefix}models? in {unit_ref} have (?:a|the)? feel no pain [1-6](?: ability)?",
        rf"{lead_prefix}models? in {unit_ref} have (?:a|the)? feel no pain [1-6](?: ability)? against psychic attacks",
        rf"{lead_prefix}models? in {unit_ref} have (?:a|the)? feel no pain [1-6](?: ability)? against psychic attacks and mortal wounds?",
        rf"{lead_prefix}models? in {unit_ref} have (?:a|the)? feel no pain [1-6](?: ability)? against mortal wounds?",
        rf"{lead_prefix}models? in {unit_ref} have (?:a|the)? feel no pain [1-6](?: ability)? against mortal wounds? and psychic attacks",
        rf"{lead_prefix}{unit_ref} has (?:a|the)? feel no pain [1-6](?: ability)?",
        rf"{lead_prefix}{unit_ref} has (?:a|the)? feel no pain [1-6](?: ability)? against psychic attacks",
        rf"{lead_prefix}{unit_ref} has (?:a|the)? feel no pain [1-6](?: ability)? against psychic attacks and mortal wounds?",
        rf"{lead_prefix}{unit_ref} has (?:a|the)? feel no pain [1-6](?: ability)? against mortal wounds?",
        rf"{lead_prefix}{unit_ref} has (?:a|the)? feel no pain [1-6](?: ability)? against mortal wounds? and psychic attacks",
        rf"{lead_prefix}(?:you can )?reroll advance rolls? made for {unit_ref} and you can reroll any rolls made for {unit_ref} while it is performing an agile (?:manoeuvre|maneuver)",
        rf"{lead_prefix}models? in {unit_ref} have (?:a|the)? [1-6] invulnerable save",
        rf"{lead_prefix}{unit_ref} has (?:a|the)? [1-6] invulnerable save",
        rf"{lead_prefix}(?:melee |ranged )?weapons equipped by models in {unit_ref} have the sustained hits \d+ ability",
        rf"{lead_prefix}add \d+ to the range characteristic of melta weapons equipped by models in {unit_ref}",
        rf"{lead_prefix}(?:melee |ranged )?(?:weapons equipped by models in|attacks made by models in) {unit_ref} .* ignores cover(?: ability)?",
        rf"{lead_prefix}each time (?:a|an) (?:melee |ranged )?attack targets {unit_ref} subtract 1 from the hit roll",
        rf"{lead_prefix}(?:while|if) {unit_ref} is within range of (?:an|one or more) objective marker(?:s)?(?: you control)? each time "
        rf"(?:a|an) (?:melee |ranged )?attack targets {unit_ref} models in (?:it|{unit_ref}) have the benefit of cover(?: against that attack)?",
        rf"{lead_prefix}each time (?:a|an) (?:melee |ranged )?attack targets {unit_ref} models in (?:it|{unit_ref}) have the benefit of cover(?: against that attack)?",
        rf"{lead_prefix}.*eligible to (?:declare a charge|charge).*",
    ]

    unsupported = [
        s for s in normalized_sentences
        if not any(re.fullmatch(p, s) for p in patterns)
    ]

    if notes:
        status = "Supported" if not unsupported else "Partial"
        return (status, " ".join(notes))
    return None


def _closest_monster_vehicle_reroll_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    base = r"each time this model makes a ranged attack that targets the closest eligible monster or vehicle target within (?P<rng>\d+)"
    wound_then_damage = rf"{base} you can reroll the wound roll(?: and you can reroll the damage roll)?"
    damage_then_wound = rf"{base} you can reroll the damage roll(?: and you can reroll the wound roll)?"
    m = re.fullmatch(wound_then_damage, norm)
    allow_wound = False
    allow_damage = False
    if m:
        allow_wound = True
        allow_damage = "damage roll" in norm
    else:
        m = re.fullmatch(damage_then_wound, norm)
        if not m:
            return None
        allow_damage = True
        allow_wound = "wound roll" in norm
    rng = m.group("rng")
    notes = []
    if allow_wound:
        notes.append(f"Ranged attacks vs closest eligible MONSTER/VEHICLE within {rng}\" can re-roll the Wound roll (optional).")
    if allow_damage:
        notes.append(f"Ranged attacks vs closest eligible MONSTER/VEHICLE within {rng}\" can re-roll the Damage roll (optional).")
    return ("Supported", " ".join(notes))


def _monster_vehicle_reroll_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    if "ranged attack" not in norm:
        return None
    if "monster or vehicle" not in norm:
        return None
    if "each time a model in this unit makes a ranged attack" not in norm:
        return None
    if "closest" in norm:
        return None
    if "reroll" not in norm:
        return None
    if not re.search(r"targets (?:an? )?(?:enemy )?monster or vehicle unit", norm):
        return None
    allow_hit = "reroll the hit roll" in norm
    allow_wound = "reroll the wound roll" in norm
    allow_damage = "reroll the damage roll" in norm
    if not (allow_hit or allow_wound or allow_damage):
        return None
    notes = []
    if "shooting phase" in norm:
        notes.append("Shooting phase only.")
    if allow_hit:
        notes.append("Ranged attacks vs MONSTER/VEHICLE can re-roll the Hit roll (optional).")
    if allow_wound:
        notes.append("Ranged attacks vs MONSTER/VEHICLE can re-roll the Wound roll (optional).")
    if allow_damage:
        notes.append("Ranged attacks vs MONSTER/VEHICLE can re-roll the Damage roll (optional).")
    return ("Supported", " ".join(notes))


def _unit_contains_oc_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"while this unit contains an? (?P<model>.+) add (?P<amt>\d+) to the objective control characteristic of models in this unit",
        norm,
    )
    if not m:
        return None
    model_name = m.group("model").strip()
    amt = m.group("amt")
    return ("Supported", f"Unit Objective Control +{amt} while it contains {model_name}.")


def _aura_objective_control_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"while a friendly (?P<kw>.+) unit is within (?P<rng>\d+) of this (?:model|unit) add (?P<amt>\d+) to the objective control characteristic of models in that unit",
        norm,
    )
    if not m:
        return None
    faction_kw = m.group("kw").strip()
    rng = m.group("rng")
    amt = m.group("amt")
    return ("Supported", f"Aura: friendly {faction_kw} within {rng}\" gain Objective Control +{amt}.")


def _aura_advance_charge_roll_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"while a friendly (?P<faction_kw>.+) units? is within (?P<rng>\d+) of this (?:model|unit) add (?P<amt>\d+) to advance and charge rolls made for (?:that|the) unit",
        norm,
    )
    if not m:
        return None
    faction_kw = m.group("faction_kw").strip()
    rng = m.group("rng")
    amt = m.group("amt")
    return ("Supported", f"Aura: friendly {faction_kw} within {rng}\" gain +{amt} to Advance and Charge rolls.")


def _aura_hit_bonus_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"while a friendly (?P<kw>.+) unit is within (?P<rng>\d+) of this (?:model|unit|bearer) "
        r"each time a model in that unit makes a (?P<atype>melee|ranged) attack add (?P<amt>\d+) to the hit roll",
        norm,
    )
    if not m:
        return None
    faction_kw = m.group("kw").strip()
    rng = m.group("rng")
    amt = m.group("amt")
    atype = m.group("atype").strip().lower()
    return ("Supported", f"Aura: friendly {faction_kw} within {rng}\" gain +{amt} to {atype} Hit rolls.")


def _aura_strength_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"while a friendly (?P<kw>.+) unit is within (?P<rng>\d+) of this (?:model|unit|bearer) "
        r"add (?P<amt>\d+) to the strength characteristic of (?:(?P<atype>melee|ranged) )?weapons equipped by models in that unit",
        norm,
    )
    if m:
        faction_kw = m.group("kw").strip()
        rng = m.group("rng")
        amt = m.group("amt")
        atype = (m.group("atype") or "any").strip().lower()
        return ("Supported", f"Aura: friendly {faction_kw} within {rng}\" gain +{amt} Strength ({atype}).")
    m = re.fullmatch(
        r"while a friendly (?P<kw>.+) unit is within (?P<rng>\d+) of this (?:model|unit|bearer) "
        r"each time a model in that unit makes a (?P<atype>melee|ranged) attack add (?P<amt>\d+) to the strength characteristic of that attack",
        norm,
    )
    if not m:
        return None
    faction_kw = m.group("kw").strip()
    rng = m.group("rng")
    amt = m.group("amt")
    atype = m.group("atype").strip().lower()
    return ("Supported", f"Aura: friendly {faction_kw} within {rng}\" gain +{amt} Strength for {atype} attacks.")


def _aura_toughness_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"while a friendly (?P<kw>.+) unit is within (?P<rng>\d+) of this (?:model|unit|bearer) "
        r"add (?P<amt>\d+) to the toughness characteristic of models in that unit",
        norm,
    )
    if m:
        faction_kw = m.group("kw").strip()
        rng = m.group("rng")
        amt = m.group("amt")
        return ("Supported", f"Aura: friendly {faction_kw} within {rng}\" gain Toughness +{amt}.")
    m = re.fullmatch(
        r"while a friendly (?P<kw>.+) unit is within (?P<rng>\d+) of this (?:model|unit|bearer) "
        r"improve the toughness characteristic of models in that unit by (?P<amt>\d+)",
        norm,
    )
    if not m:
        return None
    faction_kw = m.group("kw").strip()
    rng = m.group("rng")
    amt = m.group("amt")
    return ("Supported", f"Aura: friendly {faction_kw} within {rng}\" gain Toughness +{amt}.")


def _aura_melee_ap_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"while a friendly (?P<kw>.+) unit is within (?P<rng>\d+) of this (?:model|unit|bearer) "
        r"(?:if that unit made a charge move this turn )?"
        r"improve the armou?r penetration(?: characteristic)? of melee weapons (?:equipped by models )?in that unit by (?P<amt>\d+)",
        norm,
    )
    if not m:
        return None
    faction_kw = m.group("kw").strip()
    rng = m.group("rng")
    amt = m.group("amt")
    needs_charge = "if that unit made a charge move this turn" in norm
    note = " after a charge move this turn" if needs_charge else ""
    return ("Supported", f"Aura: friendly {faction_kw} within {rng}\" improve melee AP by {amt}{note}.")


def _bearer_invulnerable_save_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    text = _strip_html(description)
    text = text.replace("\u2019", "'")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    text = re.sub(r"\s+([.])", r"\1", text)
    m = re.fullmatch(r"the bearer has a (\d)\+ invulnerable save\.?", text, flags=re.IGNORECASE)
    if not m:
        return None
    return ("Supported", f"Bearer has a {m.group(1)}+ invulnerable save.")


def _bearer_save_characteristic_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    text = _strip_html(description)
    text = text.replace("\u2019", "'")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    text = re.sub(r"\s+([.])", r"\1", text)
    m = re.fullmatch(r"the bearer has a save characteristic of (\d)\+\.?", text, flags=re.IGNORECASE)
    if not m:
        return None
    return ("Supported", f"Bearer has a Save characteristic of {m.group(1)}+.")


def _model_fnp_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"(?:this model|the bearer) has (?:a|the)? feel no pain (?P<val>[1-6])(?: ability)?"
        r"(?: against psychic attacks(?: and mortal wounds?)?| against mortal wounds?(?: and psychic attacks)?)?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    val = m.group("val")
    return ("Supported", f"Model has Feel No Pain {val}+.")


def _bearer_smoke_keyword_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    if not re.fullmatch(r"(?:the )?bearer has the smoke keyword", norm):
        return None
    return ("Supported", "Bearer gains the SMOKE keyword.")


def _bearer_unit_keyword_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    lead_prefix = r"(?:while this model is leading a unit )?"
    pattern = rf"{lead_prefix}(?:the )?(?:bearers unit|that unit|this unit) has the grenades keyword"
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    leading = norm.startswith("while this model is leading a unit")
    prefix = "Leading: " if leading else ""
    return ("Supported", f"{prefix}Unit gains the GRENADES keyword.")


def _attached_character_fnp_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"while this model is leading a unit other character models attached to "
        r"(?:that unit|the bearers unit|this unit) have (?:the )?feel no pain ([1-6])(?: ability)?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    return ("Supported", f"Leading: other attached Character models gain Feel No Pain {m.group(1)}+.")


def _unit_contains_character_fnp_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"while this unit contains an? (?P<model>.+?) model character models in this unit have "
        r"(?:a|the)? feel no pain (?P<val>[1-6])(?: ability)?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    model = (m.group("model") or "specified model").strip()
    val = m.group("val")
    return ("Supported", f"Unit contains {model}: Character models gain Feel No Pain {val}+.")


def _leading_unit_contains_invuln_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"while this unit is leading a unit and contains an? (?P<model>.+?) model models in "
        r"(?:that unit|the bearers unit|this unit) have (?:a|the)? (?P<val>[1-6]) invulnerable save"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    model = (m.group("model") or "specified model").strip()
    val = m.group("val")
    return ("Supported", f"Leading while containing {model}: unit gains a {val}+ invulnerable save.")


def _weapon_keyword_grant_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    sentences = [
        s for s in (_norm_rules_text(part) for part in re.split(r"[.;]\s*", _strip_html(description))) if s
    ]
    if not sentences:
        return None
    lead_prefix = r"(?:while this model is leading a unit )?"
    patterns = [
        (
            rf"{lead_prefix}(?:(?P<scope>melee|ranged) )?weapons equipped by models in "
            r"(?:the bearers unit|that unit|this unit) have the (?P<keyword>[a-z0-9 ]+) ability",
            "unit",
        ),
        (
            rf"{lead_prefix}(?:the )?(?:bearers|this models) (?:(?P<scope>melee|ranged) )?weapons have the "
            r"(?P<keyword>[a-z0-9 ]+) ability",
            "bearer",
        ),
        (
            rf"{lead_prefix}(?:(?P<scope>melee|ranged) )?weapons equipped by this model have the "
            r"(?P<keyword>[a-z0-9 ]+) ability",
            "model",
        ),
    ]
    notes: List[str] = []
    unsupported: List[str] = []
    for sentence in sentences:
        leading = sentence.startswith("while this model is leading a unit")
        prefix = "Leading: " if leading else ""
        for pattern, kind in patterns:
            m = re.fullmatch(pattern, sentence)
            if not m:
                continue
            kw = m.group("keyword") or ""
            label = _attack_keyword_label_from_text(kw)
            if not label:
                unsupported.append(kw)
                continue
            scope = (m.group("scope") or "").strip().lower()
            scope_text = "weapons"
            if scope == "melee":
                scope_text = "melee weapons"
            elif scope == "ranged":
                scope_text = "ranged weapons"
            if kind == "unit":
                notes.append(f"{prefix}Unit {scope_text} gain {label}.")
            elif kind == "bearer":
                notes.append(f"{prefix}Bearer's {scope_text} gain {label}.")
            else:
                notes.append(f"{prefix}Model {scope_text} gain {label}.")
    if not notes and not unsupported:
        return None
    if unsupported:
        if notes:
            return ("Partial", " ".join(dict.fromkeys(notes)) + " Some weapon keywords are not supported.")
        return ("Partial", "Weapon keyword grants not supported for this keyword.")
    return ("Supported", " ".join(dict.fromkeys(notes)))


def _attack_roll_plus_cp_on_destroy_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    chunks, remaining = _split_attack_roll_chunks(description)
    if not chunks or not remaining:
        return None
    attack_rules = []
    for chunk in chunks:
        rule = parse_attack_roll_text(chunk)
        if rule is None:
            return None
        attack_rules.append(rule)
    cp_specs = []
    for sentence in remaining:
        spec = _cp_on_destroy_sentence(sentence)
        if spec is None:
            return None
        cp_specs.append(spec)
    if not cp_specs:
        return None

    notes = ["Attack roll modifiers supported."]
    keywords = []
    for spec in cp_specs:
        kw = spec.get("keyword")
        if kw:
            keywords.append(str(kw).upper())
    if keywords:
        notes.append(f"Gain CP on destroying {', '.join(sorted(set(keywords)))} models supported.")
    else:
        notes.append("Gain CP on destroying enemy models supported.")
    return ("Supported", " ".join(notes))


def _on_kill_battleshock_sentence(sentence: str) -> Optional[int]:
    if not sentence:
        return None
    norm = _norm_rules_text(sentence)
    if not norm:
        return None
    pattern = (
        r"each time an enemy unit is destroyed as (?:a|the) result of this (?:model|unit)(?: s|s)? attacks? "
        r"before removing the last model in that unit from the battlefield "
        r"(?:each unit from your opponent(?: s|s)? army|each enemy unit) that (?:is )?within (?P<range>\d+) of it "
        r"must take a battle shock test"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    try:
        return int(m.group("range") or 0)
    except Exception:
        return None


def _on_kill_battleshock_support(description: str) -> Optional[Tuple[str, str]]:
    rng = _on_kill_battleshock_sentence(description)
    if not rng:
        return None
    return ("Supported", f"On kill: enemy units within {rng}\" take Battle-shock tests.")


def _attack_roll_plus_on_kill_battleshock_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    chunks, remaining = _split_attack_roll_chunks(description)
    if not chunks or not remaining:
        return None
    for chunk in chunks:
        rule = parse_attack_roll_text(chunk)
        if rule is None:
            return None
    ranges: list[int] = []
    for sentence in remaining:
        rng = _on_kill_battleshock_sentence(sentence)
        if not rng:
            return None
        ranges.append(int(rng))
    if not ranges:
        return None
    unique_ranges = sorted({int(r) for r in ranges if r})
    if len(unique_ranges) == 1:
        note = f"Model attack roll modifiers supported. On kill: enemy units within {unique_ranges[0]}\" take Battle-shock tests."
    else:
        note = "Model attack roll modifiers supported. On kill: enemy units within range take Battle-shock tests."
    return ("Supported", note)


def _closest_enemy_hit_and_charge_reroll_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time a models? in this unit makes a ranged attack that targets the closest (?:eligible )?enemy unit "
        r"you can reroll the hit roll "
        r"each time this unit declares a charge that targets the closest (?:eligible )?enemy unit you can reroll the charge roll"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "Ranged attacks vs closest enemy unit: re-roll Hit roll. Charges vs closest eligible enemy unit: re-roll Charge roll.",
    )


def _attack_roll_rule_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    chunks, remaining = _split_attack_roll_chunks(description)
    if not chunks or remaining:
        return None
    rules = []
    for chunk in chunks:
        rule = parse_attack_roll_text(chunk)
        if rule is None:
            return None
        if rule.scope not in ("unit", "leading"):
            return None
        if rule.subject not in ("model_in_this_unit", "model_in_that_unit"):
            return None
        rules.append(rule)
    if not rules:
        return None
    scopes = {r.scope for r in rules}
    if scopes == {"leading"}:
        note = "Leading: attack roll modifiers supported."
    elif scopes == {"unit"}:
        note = "Unit attack roll modifiers supported."
    else:
        note = "Attack roll modifiers supported."
    return ("Supported", note)


def _ranged_ignore_bs_hit_modifiers_support(description: str) -> Optional[Tuple[str, str]]:
    """
    Support for abilities that let ranged attacks ignore any/all BS and Hit roll modifiers.

    Example:
      "Each time a model in this unit makes a ranged attack, you can ignore any or all modifiers to
       that attack's Ballistic Skill characteristic and any or all modifiers to the Hit roll."
    """
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    if "ignore any or all modifiers" not in norm:
        return None
    if "ballistic skill" not in norm or "hit roll" not in norm:
        return None
    if "weapon skill" in norm:
        return None
    if "wound roll" in norm:
        return None
    if "strength" in norm or "armour penetration" in norm or "damage" in norm:
        return None
    if "ranged attack" not in norm and "ranged weapon" not in norm:
        return None
    return ("Supported", "Ranged attacks: ignore any or all modifiers to Ballistic Skill and Hit roll.")


def _ranged_targeting_restriction_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"(?:while this model is leading a unit )?"
        r"(?:this unit|that unit|this models unit|this model s unit|the bearer s unit) "
        r"can only be selected as the target of (?:a )?ranged attacks? if the attacking model is within (?P<range>\d+)"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        pattern = (
            r"(?:while this model is leading a unit )?"
            r"(?:this unit|that unit|this models unit|this model s unit|the bearer s unit) "
            r"cannot be targeted by ranged attacks unless the attacking model is within (?P<range>\d+)"
        )
        m = re.fullmatch(pattern, norm)
    if not m:
        return None
    try:
        rng = int(m.group("range"))
    except Exception:
        rng = 0
    if rng <= 0:
        return None
    return ("Supported", f"Ranged attacks can only target this unit within {rng}\".")


def _objective_attack_keyword_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time this (?:model|unit) makes a (?:(melee|ranged) )?attack that targets (?:an? )?(?:enemy )?unit "
        r"that is within range of (?:an|one or more) objective marker(?:s)? that attack has the ([a-z0-9 ]+) ability"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    scope = (m.group(1) or "").strip().lower()
    label = _attack_keyword_label_from_text(m.group(2) or "")
    if not label:
        return None
    scope_text = "Attacks"
    if scope == "melee":
        scope_text = "Melee attacks"
    elif scope == "ranged":
        scope_text = "Ranged attacks"
    note = f"{scope_text} vs targets within objective range gain {label}."
    return ("Supported", note)


def _target_keyword_attack_keyword_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time (?:this (?:model|unit)|a model in this unit) makes a (?:(?P<scope>melee|ranged) )?attack "
        r"that targets (?:an? )?(?:enemy )?(?P<target>[a-z0-9 ]+?) unit that attack has (?:the )?(?P<keyword>[a-z0-9 ]+) ability"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    label = _attack_keyword_label_from_text(m.group("keyword") or "")
    if not label:
        return None
    target_raw = str(m.group("target") or "").strip()
    if not target_raw:
        return None
    target_raw = re.sub(r"\bunits?\b", "", target_raw).strip()
    target_raw = target_raw.replace("enemy ", "")
    parts = [p.strip() for p in re.split(r"\s+(?:or|and)\s+", target_raw) if p.strip()]
    if parts:
        target_label = "/".join(p.upper() for p in parts)
    else:
        target_label = target_raw.upper()
    scope = (m.group("scope") or "").strip().lower()
    scope_text = "Attacks"
    if scope == "melee":
        scope_text = "Melee attacks"
    elif scope == "ranged":
        scope_text = "Ranged attacks"
    note = f"{scope_text} vs {target_label} targets gain {label}."
    return ("Supported", note)


def _attack_keyword_label_from_text(raw: str) -> Optional[str]:
    kw = re.sub(r"\s+", " ", str(raw or "")).strip().lower()
    if not kw:
        return None
    if kw == "ignores cover":
        return "Ignores Cover"
    if kw == "lethal hits":
        return "Lethal Hits"
    if kw.startswith("sustained hits"):
        m_val = re.search(r"sustained hits (\d+)", kw)
        if m_val:
            return f"Sustained Hits {m_val.group(1)}"
        return None
    if kw == "devastating wounds":
        return "Devastating Wounds"
    if kw in ("twin linked", "twin-linked"):
        return "Twin-linked"
    if kw == "heavy":
        return "Heavy"
    if kw == "lance":
        return "Lance"
    if kw == "precision":
        return "Precision"
    if kw.startswith("anti "):
        m_val = re.search(r"anti ([a-z0-9 ]+) (\\d+)", kw)
        if m_val:
            anti_kw = m_val.group(1).strip().upper().replace(" ", "-")
            return f"Anti-{anti_kw} {m_val.group(2)}+"
    return None


def _half_range_attack_keyword_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    sentences = [
        s for s in (_norm_rules_text(part) for part in re.split(r"[.;]\s*", _strip_html(description))) if s
    ]
    if not sentences:
        return None
    lead_prefix = r"(?:while this model is leading a unit )?"
    patterns = [
        (
            rf"{lead_prefix}each time this (?:model|unit) makes a (?:(?P<scope>melee|ranged) )?attack "
            r"that targets (?:an? )?(?:enemy )?unit within half range(?:, )?that attack has the "
            r"(?P<keyword>[a-z0-9 ]+) ability",
            "attack",
        ),
        (
            rf"{lead_prefix}(?:(?P<scope>melee|ranged) )?weapons equipped by models in "
            r"(?:the bearers unit|that unit|this unit) have the (?P<keyword>[a-z0-9 ]+) ability.* within half range",
            "unit_weapons",
        ),
        (
            rf"{lead_prefix}(?:(?P<scope>melee|ranged) )?weapons equipped by this model have the "
            r"(?P<keyword>[a-z0-9 ]+) ability.* within half range",
            "model_weapons",
        ),
        (
            rf"{lead_prefix}this models (?P<weapons>.+?) (?:have|has) the (?P<keyword>[a-z0-9 ]+) ability.* within half range",
            "weapon_list",
        ),
    ]
    notes = []
    for sentence in sentences:
        matched = False
        leading = sentence.startswith("while this model is leading a unit")
        prefix = "Leading: " if leading else ""
        for pattern, kind in patterns:
            m = re.fullmatch(pattern, sentence)
            if not m:
                continue
            label = _attack_keyword_label_from_text(m.group("keyword") or "")
            if not label:
                return None
            scope = (m.groupdict().get("scope") or "").strip().lower()
            if kind == "attack":
                scope_text = "Attacks"
                if scope == "melee":
                    scope_text = "Melee attacks"
                elif scope == "ranged":
                    scope_text = "Ranged attacks"
                notes.append(f"{prefix}{scope_text} vs targets within half range gain {label}.")
            elif kind == "unit_weapons":
                if scope:
                    notes.append(f"{prefix}Unit {scope} weapons gain {label} at half range.")
                else:
                    notes.append(f"{prefix}Unit weapons gain {label} at half range.")
            elif kind == "model_weapons":
                if scope:
                    notes.append(f"{prefix}This model's {scope} weapons gain {label} at half range.")
                else:
                    notes.append(f"{prefix}This model's weapons gain {label} at half range.")
            else:
                notes.append(f"{prefix}Listed weapons gain {label} at half range.")
            matched = True
            break
        if not matched:
            return None
    if not notes:
        return None
    return ("Supported", " ".join(notes))


def _model_reroll_wound_vs_character_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    raw = _strip_html(description)
    if not raw:
        return None
    sentences = [s.strip() for s in re.split(r"[.;]\s*", raw) if s.strip()]
    if not sentences:
        return None

    cp_pattern = (
        r"each time (?:this model|this models unit|this unit) destroys an? (?:enemy )?character (?:model|unit) you gain \d+ ?cp"
    )

    hit_reroll = False
    wound_reroll = False
    keyword_signatures: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    cp_on_kill = False

    for sentence in sentences:
        norm_sentence = _norm_rules_text(sentence)
        if re.fullmatch(cp_pattern, norm_sentence):
            cp_on_kill = True
            continue
        rule = parse_attack_roll_text(sentence)
        if rule is None:
            return None
        if rule.subject != "this_model":
            return None
        if rule.attack_type not in ("any", "melee", "ranged"):
            return None
        if not rule.effects:
            return None
        for eff in rule.effects:
            if eff.kind != "reroll" or eff.roll not in ("hit", "wound"):
                return None
            if not eff.reroll_full:
                return None
            cond = eff.condition
            if not cond or not (cond.target_keywords_any or cond.target_keywords_all):
                return None
            kw_any = tuple(sorted({k.strip().lower() for k in (cond.target_keywords_any or ()) if k}))
            kw_all = tuple(sorted({k.strip().lower() for k in (cond.target_keywords_all or ()) if k}))
            keyword_signatures.add((kw_any, kw_all))
            if eff.roll == "hit":
                hit_reroll = True
            else:
                wound_reroll = True

    if not (hit_reroll or wound_reroll):
        return None

    target_label = "keyword-conditioned targets"
    if len(keyword_signatures) == 1:
        kw_any, kw_all = next(iter(keyword_signatures))
        if kw_any:
            target_label = "/".join(k.upper() for k in kw_any) + " units"
        elif kw_all:
            target_label = " & ".join(k.upper() for k in kw_all) + " units"

    notes = []
    if hit_reroll:
        notes.append(f"Model attacks vs {target_label} can re-roll the Hit roll (optional).")
    if wound_reroll:
        notes.append(f"Model attacks vs {target_label} can re-roll the Wound roll (optional).")
    if cp_on_kill:
        notes.append("Gain CP on destroying CHARACTER models supported.")
    return ("Supported", " ".join(notes))


def _model_hit_bonus_vs_fly_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"each time this model makes (?:a|an)?(?: melee| ranged)? attacks? that targets? a unit that can fly add (?P<amt>\d+) to the hit roll",
        norm,
    )
    if not m:
        return None
    return ("Supported", f"Model attacks vs FLY targets gain +{m.group('amt')} to hit.")


def _start_of_battle_keyword_reroll_ones_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the start of the battle select one of the following keywords (?P<keywords>[a-z0-9 ]+) "
        r"each time this model makes an attack that targets a unit with the selected keyword reroll a hit roll of 1 "
        r"and reroll a wound roll of 1"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    tokens = [t for t in str(m.group("keywords") or "").split() if t]
    allowed = {"infantry", "monster", "mounted", "vehicle"}
    found = []
    for token in tokens:
        if token in allowed and token.upper() not in found:
            found.append(token.upper())
    if found:
        keywords_label = ", ".join(found)
        note = f"Start of battle: select one of {keywords_label}; re-roll Hit/Wound rolls of 1 vs that keyword."
    else:
        note = "Start of battle: select a keyword; re-roll Hit/Wound rolls of 1 vs that keyword."
    return ("Supported", note)


def _battle_focus_agile_maneuver_token_refund_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"while this model is leading a unit each time you spend a battle focus token to enable that unit to perform "
        r"an agile (?:manoeuvre|maneuver) roll (?:one|1|a) d6 on a (?P<threshold>\d) you gain 1 battle focus token"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    threshold = m.group("threshold") or "3"
    return (
        "Supported",
        f"While leading: when spending a Battle Focus token for an Agile Manoeuvre, roll a D6; on {threshold}+ gain 1 token.",
    )


def _leading_leadership_reroll_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = r"while this model is leading a unit you can reroll leadership tests taken for that unit"
    if not re.fullmatch(pattern, norm):
        return None
    return ("Supported", "Leading: re-roll Leadership tests taken for the unit.")


def _dark_pacts_leadership_reroll_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = r"each time the bearers unit takes a leadership test for the dark pacts ability you can reroll that test"
    if not re.fullmatch(pattern, norm):
        return None
    return ("Supported", "Dark Pacts: re-roll the Leadership test for the Dark Pacts ability.")


def _defensive_wound_penalty_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"(?:while (?:(?:a|an|the) [a-z0-9 ]+|this)(?: model)? is leading (?:this|a) unit )?"
        r"each time (?:an|a) (?:(?P<atype>melee|ranged) )?attack(?:s)? "
        r"(?:targets|target|is allocated to) "
        r"(?P<scope>this model|this unit|this model s unit|a model in this unit) "
        r"subtract (?P<val>\d+) from (?:the|that|that attacks) wound roll(?:s)?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    val = m.group("val")
    scope_raw = m.group("scope") or "this model"
    scope_text = "Model" if "model" in scope_raw else "Unit"
    atype = (m.group("atype") or "").strip().lower()
    if atype == "melee":
        attack_scope = "melee"
    elif atype == "ranged":
        attack_scope = "ranged"
    else:
        attack_scope = "all"
    return ("Supported", f"{scope_text} targeted: -{val} to wound vs {attack_scope} attacks.")


def _defensive_strength_gt_toughness_wound_penalty_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"(?:while (?:(?:a|an|the) [a-z0-9 ]+|this)(?: model)? is leading (?:this|a) unit )?"
        r"each time (?:an|a) (?:(?P<atype>melee|ranged) )?attack(?:s)? "
        r"(?:targets|target|is allocated to) "
        r"(?P<scope>this model|this unit|this model s unit|a model in this unit) "
        r"if (?:the )?(?:strength characteristic of that attack|that attacks strength characteristic) "
        r"is greater than "
        r"(?:the toughness characteristic of (?:this model|this unit|that model)|(?:this model|this unit|that model)s toughness characteristic) "
        r"subtract (?P<val>\d+) from (?:the|that|that attacks) wound roll(?:s)?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    val = m.group("val")
    scope_raw = m.group("scope") or "this model"
    scope_text = "Model" if "model" in scope_raw else "Unit"
    atype = (m.group("atype") or "").strip().lower()
    if atype == "melee":
        attack_scope = "melee"
    elif atype == "ranged":
        attack_scope = "ranged"
    else:
        attack_scope = "all"
    return ("Supported", f"{scope_text} targeted: -{val} to wound vs {attack_scope} attacks when S > T.")


def _model_attack_roll_bonus_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    chunks, remaining = _split_attack_roll_chunks(description)
    if not chunks or remaining:
        return None
    rules: list[Any] = []
    for chunk in chunks:
        rule = parse_attack_roll_text(chunk)
        if rule is None:
            return None
        if rule.subject != "this_model":
            return None
        if rule.scope not in ("unit", "leading"):
            return None
        if rule.attack_type not in ("melee", "ranged", "any"):
            return None
        for eff in rule.effects:
            if eff.roll not in ("hit", "wound"):
                return None
            if eff.kind not in ("add", "sub"):
                return None
        rules.append(rule)
    if not rules:
        return None
    hit = any(eff.roll == "hit" for rule in rules for eff in rule.effects)
    wound = any(eff.roll == "wound" for rule in rules for eff in rule.effects)
    if not (hit or wound):
        return None
    scopes = {r.scope for r in rules}
    prefix = "Leading: " if scopes == {"leading"} else ""
    if hit and wound:
        note = f"{prefix}Model attack roll modifiers (+hit/+wound) supported."
    elif hit:
        note = f"{prefix}Model attack roll modifiers (+hit) supported."
    else:
        note = f"{prefix}Model attack roll modifiers (+wound) supported."
    return ("Supported", note)


def _model_target_strength_hit_wound_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    rule = parse_attack_roll_text(description)
    if rule is None:
        return None
    if rule.subject != "this_model":
        return None
    if rule.attack_type not in ("melee", "any"):
        return None
    if rule.scope not in ("unit", "leading"):
        return None
    hit_ok = False
    wound_ok = False
    for eff in rule.effects:
        if eff.roll not in ("hit", "wound"):
            continue
        if eff.kind not in ("add", "sub"):
            continue
        cond = eff.condition
        if not cond:
            continue
        if eff.roll == "hit" and cond.target_below_starting_strength:
            hit_ok = True
        if eff.roll == "wound" and cond.target_below_half_strength:
            wound_ok = True
    if not (hit_ok and wound_ok):
        return None
    return (
        "Supported",
        "Model melee attacks vs weakened targets: +hit below Starting Strength, +wound below Half-strength.",
    )


def _model_self_strength_hit_wound_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    rule = parse_attack_roll_text(description)
    if rule is None:
        return None
    if rule.subject != "this_model":
        return None
    if rule.attack_type not in ("melee", "ranged", "any"):
        return None
    if rule.scope not in ("unit", "leading"):
        return None
    hit_ok = False
    wound_ok = False
    for eff in rule.effects:
        if eff.roll not in ("hit", "wound"):
            continue
        if eff.kind != "add":
            continue
        cond = eff.condition
        if not cond:
            continue
        if eff.roll == "hit" and cond.attacker_below_starting_strength:
            hit_ok = True
        if eff.roll == "wound" and cond.attacker_below_half_strength:
            wound_ok = True
    if not (hit_ok or wound_ok):
        return None
    notes = []
    if hit_ok:
        notes.append("Model attacks while below Starting Strength: hit bonus supported.")
    if wound_ok:
        notes.append("Model attacks while below Half-strength: wound bonus supported.")
    return ("Supported", " ".join(notes))


def _charge_end_mortal_wounds_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None

    per_model = (
        r"each time (?:this models unit|this unit) ends a charge move select one enemy unit within engagement range of (?:this unit|this model) "
        r"(?:then |and (?:then )?)?roll one d6 for each model in (?:this unit|that unit|this models unit) for each 4\+? that enemy unit suffers d3 mortal wounds?"
    )
    table = (
        r"each time (?:this models unit|this unit) ends a charge move select one enemy unit within engagement range of (?:this unit|this model) "
        r"(?:then |and (?:then )?)?roll one d6 on a 2 3 that enemy unit suffers 1 mortal wounds? on a 4 5 that enemy unit suffers d3 mortal wounds? on a 6 that enemy unit suffers d3 3 mortal wounds?"
    )
    remaining_wounds = (
        r"each time this model ends a charge move select one enemy unit within engagement range of it "
        r"(?:then |and (?:then )?)?roll one d6 for each of this models remaining wounds for each 4 that enemy unit suffers 1 mortal wounds?"
        r"(?: to a maximum of 6 mortal wounds?)?"
    )
    if re.fullmatch(per_model, norm):
        return (
            "Supported",
            "Charge end: pick an engaged enemy; D6 per model, each 4+ inflicts D3 mortal wounds.",
        )
    if re.fullmatch(table, norm):
        return (
            "Supported",
            "Charge end: pick an engaged enemy; D6 table for mortal wounds (2-3=1, 4-5=D3, 6=D3+3).",
        )
    if re.fullmatch(remaining_wounds, norm):
        return (
            "Supported",
            "Charge end: pick an engaged enemy; D6 per remaining wound, each 4+ inflicts 1 mortal wound (max 6).",
        )
    return None


def _selected_to_shoot_single_reroll_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if "selected to shoot" not in norm:
        return None
    if "selected to shoot or fight" in norm or "selected to fight" in norm:
        return None
    if "reroll" not in norm:
        return None
    allow_hit = bool(re.search(r"reroll\s+one\s+hit\s+roll", norm))
    allow_wound = bool(re.search(r"reroll\s+one\s+wound\s+roll", norm))
    allow_damage = bool(re.search(r"reroll\s+one\s+damage\s+roll", norm))
    if not (allow_hit or allow_wound or allow_damage):
        return None
    notes = []
    if allow_hit:
        notes.append("Selected to shoot: can re-roll one Hit roll (optional).")
    if allow_wound:
        notes.append("Selected to shoot: can re-roll one Wound roll (optional).")
    if allow_damage:
        notes.append("Selected to shoot: can re-roll one Damage roll (optional).")
    return ("Supported", " ".join(notes))


def _selected_to_shoot_or_fight_reroll_choice_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    if not (
        re.search(r"selected\s+to\s+(?:shoot|fire)\s+or\s+fight", norm)
        or re.search(r"selected\s+to\s+fight\s+or\s+(?:shoot|fire)", norm)
    ):
        return None
    if "reroll" not in norm:
        return None
    allow_hit = bool(re.search(r"reroll\s+one\s+hit\s+roll", norm))
    allow_wound = bool(re.search(r"reroll\s+one\s+wound\s+roll", norm))
    if not (allow_hit and allow_wound):
        return None
    if not re.search(r"hit\s+roll.*or.*wound\s+roll|wound\s+roll.*or.*hit\s+roll", norm):
        return None
    return (
        "Supported",
        "Selected to shoot or fight: can re-roll one Hit roll or one Wound roll (optional).",
    )


def _fight_within_3_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time this models unit is selected to fight you can use this ability .* eligible to fight .* within 3 .* eligible to fight .* within engagement range .*"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "Optional fight activation: models within 3\" of enemy models can fight eligible engaged targets.",
    )


def _allocated_damage_reduction_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    base = r"each time (?:a|an) (?:melee |ranged )?attack is allocated to (?:this model|a model in this unit)"
    half_patterns = [
        rf"{base} (?:halve|half) the damage characteristic of that attack",
        rf"{base} the damage characteristic of that attack is halved",
        rf"{base} .* damage characteristic .* halved",
    ]
    sub_pattern = rf"{base} subtract (?P<val>\d+) from the damage characteristic of that attack"
    if any(re.fullmatch(p, norm) for p in half_patterns):
        atype = ""
        m2 = re.search(r"each time (?:a|an) (melee|ranged) attack is allocated", norm)
        if m2:
            atype = m2.group(1).lower()
        if atype:
            return ("Supported", f"Allocated {atype} attacks have Damage halved.")
        return ("Supported", "Allocated attacks have Damage halved.")
    m = re.fullmatch(sub_pattern, norm)
    if not m:
        return None
    atype = ""
    m2 = re.search(r"each time (?:a|an) (melee|ranged) attack is allocated", norm)
    if m2:
        atype = m2.group(1).lower()
    if atype:
        return ("Supported", f"Allocated {atype} attacks have -{m.group('val')} Damage.")
    return ("Supported", f"Allocated attacks have -{m.group('val')} Damage.")


def _targeted_stratagem_cp_discount_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    direct_patterns = [
        (
            r"once per battle round one (?:unit|model) from your army with this ability can use it when "
            r"(?:its unit|this models unit|that models unit) is targeted with a stratagem(?: if it does)? reduce the cp cost of that "
            r"(?:use|usage) of that stratagem by 1 ?cp"
        ),
        (
            r"once per battle round you can select one model from your army with this ability "
            r"(?:that models unit can be targeted with a stratagem|and target that models unit with a stratagem) "
            r"(?:if it does)? reduce the cp cost of that (?:use|usage) of that stratagem by 1 ?cp"
        ),
    ]
    aura_pattern = (
        r"once per battle round one (?:unit|model) from your army with this ability can use it when a friendly "
        r"(?P<keyword>[a-z0-9 ]+?) unit within (?P<range>\d+) of (?:that|this) model is targeted with a stratagem(?: if it does)? "
        r"reduce the cp cost of that (?:use|usage) of that stratagem by 1 ?cp"
    )
    aura_alt_pattern = (
        r"once per battle round when a friendly (?P<keyword>[a-z0-9 ]+?) unit within (?P<range>\d+) of this model is targeted with a "
        r"stratagem this model can use this ability(?: if it does)? reduce the cp cost of that (?:use|usage) of that stratagem by 1 ?cp"
    )
    aura_alt2_pattern = (
        r"once per battle round one friendly (?P<keyword>[a-z0-9 ]+?) unit within (?P<range>\d+) of this model can be targeted with a "
        r"stratagem(?: if it does)? reduce the cp cost of that (?:use|usage) of that stratagem by 1 ?cp"
    )
    for pattern in (*direct_patterns, aura_pattern, aura_alt_pattern, aura_alt2_pattern):
        m = re.fullmatch(pattern, norm)
        if not m:
            continue
        if "keyword" in m.groupdict():
            kw = re.sub(r"\s+", " ", (m.group("keyword") or "").strip())
            rng = m.group("range") or "0"
            kw_label = kw.upper() if kw else "friendly"
            return (
                "Supported",
                f"Once per battle round, when a friendly {kw_label} unit within {rng}\" is targeted with a Stratagem, reduce its CP cost by 1.",
            )
        return (
            "Supported",
            "Once per battle round, when this unit is targeted with a Stratagem, you can reduce its CP cost by 1.",
        )
    return None


def _targeted_stratagem_cp_increase_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    if "opponent" not in norm:
        return None
    if "stratagem" not in norm or "increase" not in norm or "cp cost" not in norm:
        return None
    if ("target" not in norm and "uses a stratagem" not in norm) or "within" not in norm:
        return None
    if not re.search(r"increase .* cp cost .* stratagem", norm):
        return None
    m = re.search(r"within (?P<range>\d+) of (?:this model|the bearer|this unit)", norm)
    rng = m.group("range") if m else "?"
    return (
        "Supported",
        f"Opponent stratagems targeting units within {rng}\" have +1CP (non-cumulative; unaffordable stratagems still count as used).",
    )


def _brutal_example_overwatch_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    required = (
        "fire overwatch",
        "stratagem",
        "0cp",
        "once per turn",
        "bodyguard",
        "destroyed",
        "leading",
        "traitor enforcer",
    )
    if not all(token in norm for token in required):
        return None
    return (
        "Supported",
        "Once per turn while leading and containing a Traitor Enforcer: Fire Overwatch for 0CP even if already used this turn; destroy 1 Bodyguard model.",
    )


def _leading_unit_common_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    text = _strip_html(description)
    text = text.replace("\u2019", "'").replace("\u0192?T", "'")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    low = text.lower()
    if not re.search(r"while this model is leading(?:s)?(?: a)? .*? unit", low, flags=re.IGNORECASE):
        return None
    if (
        "model in that unit" not in low
        and "models in that unit" not in low
        and "that unit has" not in low
        and "that unit have" not in low
    ):
        return None

    normalized = _norm_rules_text(text)
    unmodified_pattern = (
        r"while this model is leading a unit once per phase you can change the result of one hit roll one wound roll or one "
        r"damage roll made for a model in that unit(?: excluding support weapon models)? to an unmodified 6"
    )
    if re.fullmatch(unmodified_pattern, normalized):
        note = "Leading: once per phase, can set one Hit/Wound/Damage roll to an unmodified 6."
        if "excluding support weapon models" in normalized:
            note = "Leading: once per phase, can set one Hit/Wound/Damage roll to an unmodified 6 (excluding Support Weapon models)."
        return ("Supported", note)
    overlord_pattern = (
        r"while this model is leading a unit each time a model in that unit makes an attack reroll a wound roll of 1 "
        r"while that unit is below its starting strength each time a model in that unit makes an attack you can reroll the wound roll instead"
    )
    if re.fullmatch(overlord_pattern, normalized):
        return (
            "Supported",
            "Leading: re-roll Wound rolls of 1; while below Starting Strength, re-roll the Wound roll instead.",
        )
    notes: List[str] = []
    lethal_melee = re.search(
        r"melee weapons equipped by models in that unit have the \[?lethal hits\]? ability",
        low,
        flags=re.IGNORECASE,
    )
    lethal_ranged = re.search(
        r"ranged weapons equipped by models in that unit have the \[?lethal hits\]? ability",
        low,
        flags=re.IGNORECASE,
    )
    lethal_any = re.search(
        r"weapons equipped by models in that unit have the \[?lethal hits\]? ability",
        low,
        flags=re.IGNORECASE,
    )
    if lethal_melee:
        notes.append("Leading: unit melee weapons gain Lethal Hits.")
    elif lethal_ranged:
        notes.append("Leading: unit ranged weapons gain Lethal Hits.")
    elif lethal_any:
        notes.append("Leading: unit weapons gain Lethal Hits.")

    fight_first_match = re.search(
        r"(?:models in that unit|that unit)\s+(?:has|have)\s+(?:the\s+)?fights?\s+first\s+ability",
        low,
        flags=re.IGNORECASE,
    )
    if fight_first_match:
        notes.append("Leading: unit gains Fights First.")

    invuln_match = re.search(
        r"models in that unit have (?:a|the)?\s*(\d)\+\s*invulnerable save",
        low,
        flags=re.IGNORECASE,
    )
    if invuln_match:
        notes.append(f"Leading: unit models gain {invuln_match.group(1)}+ invulnerable save.")

    if "melee attack" in low:
        attack_scope = "melee"
    elif "ranged attack" in low:
        attack_scope = "ranged"
    else:
        attack_scope = "all"

    hit_conditional = False
    wound_conditional = False
    m = re.search(
        r"add\s+(\d+)\s+to\s+the\s+hit\s+roll\s+if\s+that\s+unit\s+is\s+below\s+(?:its\s+)?starting\s+strength",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        hit_conditional = True
        notes.append(f"Leading: +{m.group(1)} to hit for {attack_scope} attacks while below Starting Strength.")
    m = re.search(
        r"add\s+(\d+)\s+to\s+the\s+wound\s+roll(?:\s+as\s+well)?\s+if\s+that\s+unit\s+is\s+below\s+half[- ]strength",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        wound_conditional = True
        notes.append(f"Leading: +{m.group(1)} to wound for {attack_scope} attacks while below Half-strength.")
    m = re.search(
        r"add\s+(\d+)\s+to\s+the\s+wound\s+roll(?:\s+as\s+well)?\s+if\s+the\s+target\s+is\s+battle[- ]shocked",
        low,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"if\s+the\s+target\s+is\s+battle[- ]shocked,\s+add\s+(\d+)\s+to\s+the\s+wound\s+roll",
            low,
            flags=re.IGNORECASE,
        )
    if m:
        wound_conditional = True
        notes.append(f"Leading: +{m.group(1)} to wound for {attack_scope} attacks vs Battle-shocked targets.")

    if not hit_conditional:
        m = re.search(
            r"each time a model in that unit makes (?:a|an)\s+(?:melee|ranged)?\s*attack, add\s+(\d+)\s+to\s+the\s+hit\s+roll",
            low,
            flags=re.IGNORECASE,
        )
        if m:
            notes.append(f"Leading: +{m.group(1)} to hit for {attack_scope} attacks.")

    if not wound_conditional:
        m = re.search(
            r"each time a model in that unit makes (?:a|an)\s+(?:melee|ranged)?\s*attack, add\s+(\d+)\s+to\s+the\s+wound\s+roll",
            low,
            flags=re.IGNORECASE,
        )
        if m:
            notes.append(f"Leading: +{m.group(1)} to wound for {attack_scope} attacks.")

    hit_re = re.search(r"re-?roll (?:a|any)?\s*hit roll(?:s)? of 1", low, flags=re.IGNORECASE)
    wound_re = re.search(r"re-?roll (?:a|any)?\s*wound roll(?:s)? of 1", low, flags=re.IGNORECASE)
    if hit_re and wound_re:
        notes.append(f"Leading: re-roll Hit/Wound rolls of 1 for {attack_scope} attacks.")

    normalized_sentences = []
    for sentence in re.split(r"[.;]\s*", _strip_html(description)):
        norm_sentence = _norm_rules_text(sentence)
        if norm_sentence:
            normalized_sentences.append(norm_sentence)

    lead_prefix = r"(?:while this model is leading(?:s)?(?: a)? .*? unit )?"
    patterns = [
        rf"{lead_prefix}melee weapons equipped by models in that unit have the lethal hits ability",
        rf"{lead_prefix}ranged weapons equipped by models in that unit have the lethal hits ability",
        rf"{lead_prefix}weapons equipped by models in that unit have the lethal hits ability",
        rf"{lead_prefix}(?:models in that unit|that unit) (?:has|have) (?:the )?fights? first ability",
        rf"{lead_prefix}each time a model in that unit makes (?:a|an)?(?: melee| ranged)? attack(?:s)? add \d+ to the hit roll if that unit is below (?:its )?starting strength and add \d+ to the wound roll(?: as well)? if that unit is below (?:its )?half strength",
        rf"{lead_prefix}each time a model in that unit makes (?:a|an)?(?: melee| ranged)? attack add \d+ to the hit roll",
        rf"{lead_prefix}each time a model in that unit makes (?:a|an)?(?: melee| ranged)? attack add \d+ to the wound roll",
        rf"{lead_prefix}add \d+ to the hit roll if that unit is below (?:its )?starting strength",
        rf"{lead_prefix}add \d+ to the wound roll(?: as well)? if that unit is below half strength",
        rf"{lead_prefix}add \d+ to the wound roll(?: as well)? if the target is battle shocked",
        rf"{lead_prefix}if the target is battle shocked add \d+ to the wound roll",
        rf"{lead_prefix}models in that unit have (?:a|the)?\s*\d+ invulnerable save",
        rf"{lead_prefix}.*reroll .*hit roll.* of 1.*",
        rf"{lead_prefix}.*reroll .*wound roll.* of 1.*",
    ]

    unsupported = [
        s for s in normalized_sentences
        if not any(re.fullmatch(p, s) for p in patterns)
    ]

    if notes:
        status = "Supported" if not unsupported else "Partial"
        return (status, " ".join(notes))
    return None


def _unit_hit_reroll_ones_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    text = _strip_html(description)
    text = text.replace("\u2019", "'").replace("\u0192?T", "'")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    low = text.lower()
    if "model in this unit" not in low:
        return None
    if "leading a unit" in low:
        return None
    text = re.sub(r";\s*", ". ", text)

    def _split_sentences(text_value: str) -> List[str]:
        return [part.strip() for part in re.split(r"\.\s*", text_value) if part.strip()]

    sentences = _split_sentences(text)
    if not sentences:
        return None

    base_typed_re = re.compile(
        r"^each time a model in this unit makes (?:a|an) (?P<atype>melee|ranged) attack(?:s)?"
        r"[,;:]?\s*(?:you can\s*)?re-?roll (?:a|any)?\s*hit roll(?:s)? of 1$",
        re.IGNORECASE,
    )
    base_any_re = re.compile(
        r"^each time a model in this unit makes (?:a|an) attack(?:s)?"
        r"[,;:]?\s*(?:you can\s*)?re-?roll (?:a|any)?\s*hit roll(?:s)? of 1$",
        re.IGNORECASE,
    )
    objective_clause_re = re.compile(
        r"^if (?:that attack targets|the target of that attack is) (?:a unit )?(?:that is )?"
        r"within range of (?:an|one or more) objective marker(?:s)?"
        r"\s*[,;:]?\s*(?:you can\s*)?re-?roll the hit roll instead$",
        re.IGNORECASE,
    )
    closest_clause_re = re.compile(
        r"^if (?:that attack targets|the target of that attack is) the closest (?:eligible )?(?:enemy )?(?:unit|target)"
        r"\s*[,;:]?\s*(?:you can\s*)?re-?roll the hit roll instead$",
        re.IGNORECASE,
    )

    base_sentences: List[str] = []
    base_atype = None
    multiple_bases = False
    for sentence in sentences:
        s_low = sentence.lower()
        if "model in this unit" not in s_low:
            continue
        m = base_typed_re.match(s_low)
        if m:
            base_sentences.append(sentence)
            if base_atype is None:
                base_atype = m.group("atype").lower()
            else:
                multiple_bases = True
            continue
        if base_any_re.match(s_low):
            base_sentences.append(sentence)
            if base_atype is None:
                base_atype = "all"
            else:
                multiple_bases = True

    if not base_sentences:
        return None

    if base_atype == "melee":
        attack_scope = "melee"
    elif base_atype == "ranged":
        attack_scope = "ranged"
    else:
        attack_scope = "all"

    notes = [f"Unit attacks re-roll Hit rolls of 1 for {attack_scope} attacks."]
    objective_sentences = [s for s in sentences if objective_clause_re.match(s.lower())]
    closest_sentences = [s for s in sentences if closest_clause_re.match(s.lower())]
    unsupported = [
        s
        for s in sentences
        if s not in base_sentences
        and not objective_clause_re.match(s.lower())
        and not closest_clause_re.match(s.lower())
    ]

    if objective_sentences:
        notes.append("If the target is within range of an objective marker, the Hit roll can be re-rolled instead (optional).")
    if closest_sentences:
        notes.append("If the target is the closest eligible target, the Hit roll can be re-rolled instead (optional).")

    if multiple_bases or unsupported:
        notes.append("Additional clauses not handled.")
        return ("Partial", " ".join(notes))

    return ("Supported", " ".join(notes))


def _unit_wound_reroll_ones_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    text = _strip_html(description)
    text = text.replace("\u2019", "'").replace("\u0192?T", "'")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    low = text.lower()
    if "model in this unit" not in low:
        return None
    if "leading a unit" in low:
        return None
    text = re.sub(r";\s*", ". ", text)

    def _split_sentences(text_value: str) -> List[str]:
        return [part.strip() for part in re.split(r"\.\s*", text_value) if part.strip()]

    sentences = _split_sentences(text)
    if not sentences:
        return None

    base_typed_re = re.compile(
        r"^each time a model in this unit (?:makes (?:a|an) |targets (?:an?|the)?\s*(?:enemy\s+)?unit with (?:a|an) )"
        r"(?P<atype>melee|ranged) attack(?:s)?[,;:]?\s*(?:you can\s*)?re-?roll (?:a|any)?\s*wound roll(?:s)? of 1$",
        re.IGNORECASE,
    )
    base_any_re = re.compile(
        r"^each time a model in this unit (?:makes (?:a|an) attack|targets (?:an?|the)?\s*(?:enemy\s+)?unit with an attack)"
        r"[,;:]?\s*(?:you can\s*)?re-?roll (?:a|any)?\s*wound roll(?:s)? of 1$",
        re.IGNORECASE,
    )
    objective_clause_re = re.compile(
        r"^if (?:that attack targets|the target of that attack is|that enemy unit is) (?:a unit )?(?:that is )?"
        r"within range of (?:an|one or more) objective marker(?:s)?"
        r"\s*[,;:]?\s*(?:you can\s*)?re-?roll the wound roll instead$",
        re.IGNORECASE,
    )
    objective_unit_clause_re = re.compile(
        r"^while this unit is within range of an objective marker you control"
        r"\s*[,;:]?\s*(?:you can\s*)?re-?roll the wound roll instead$",
        re.IGNORECASE,
    )

    base_sentences: List[str] = []
    base_atype = None
    multiple_bases = False
    for sentence in sentences:
        s_low = sentence.lower()
        if "model in this unit" not in s_low:
            continue
        m = base_typed_re.match(s_low)
        if m:
            base_sentences.append(sentence)
            if base_atype is None:
                base_atype = m.group("atype").lower()
            else:
                multiple_bases = True
            continue
        if base_any_re.match(s_low):
            base_sentences.append(sentence)
            if base_atype is None:
                base_atype = "all"
            else:
                multiple_bases = True

    if not base_sentences:
        return None

    if base_atype == "melee":
        attack_scope = "melee"
    elif base_atype == "ranged":
        attack_scope = "ranged"
    else:
        attack_scope = "all"

    notes = [f"Unit attacks re-roll Wound rolls of 1 for {attack_scope} attacks."]
    objective_sentences = [
        s
        for s in sentences
        if objective_clause_re.match(s.lower()) or objective_unit_clause_re.match(s.lower())
    ]
    unsupported = [
        s
        for s in sentences
        if s not in base_sentences
        and not objective_clause_re.match(s.lower())
        and not objective_unit_clause_re.match(s.lower())
    ]

    if objective_sentences:
        notes.append("If the target is within range of an objective marker, the Wound roll can be re-rolled instead (optional).")

    if multiple_bases or unsupported:
        notes.append("Additional clauses not handled.")
        return ("Partial", " ".join(notes))

    return ("Supported", " ".join(notes))


def _target_hit_roll_penalty_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    text = _strip_html(description)
    text = text.replace("\u2019", "'").replace("\u0192?T", "'")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    text = re.sub(r";\s*", ". ", text)
    sentences = [part.strip() for part in re.split(r"\.\s*", text) if part.strip()]
    if not sentences:
        return None

    prefix = r"(?:while this (?:model|unit) is leading (?:a|this) unit, )?"
    unit_re = re.compile(
        prefix
        + r"each time (?:a|an) (?:(?P<atype>melee|ranged) )?attack "
        r"(?:targets|is made against) (?:this unit|that unit|the bearer'?s unit), subtract 1 from the hit roll(?P<tail>.*)$",
        re.IGNORECASE,
    )
    model_re = re.compile(
        prefix
        + r"each time (?:a|an) (?:(?P<atype>melee|ranged) )?attack "
        r"(?:targets|is made against) this model, subtract 1 from the hit roll(?P<tail>.*)$",
        re.IGNORECASE,
    )

    matched: List[str] = []
    notes: List[str] = []
    partial = False

    def _note(scope: str, atype: Optional[str]) -> None:
        if atype == "melee":
            scope_text = "melee"
        elif atype == "ranged":
            scope_text = "ranged"
        else:
            scope_text = "all"
        notes.append(f"{scope} targeted: -1 to hit vs {scope_text} attacks.")

    for sentence in sentences:
        sl = sentence.lower()
        if not sl.startswith("each time"):
            continue
        if any(x in f" {sl} " for x in (" if ", " unless ", " while ", " when ")):
            continue
        for scope, pattern in (("Unit", unit_re), ("Model", model_re)):
            m = pattern.match(sl)
            if not m:
                continue
            matched.append(sentence)
            _note(scope, (m.group("atype") or "").lower() or None)
            tail = (m.group("tail") or "").strip().strip(" .;")
            if tail:
                partial = True
            break

    if not matched:
        return None

    if any(s for s in sentences if s not in matched):
        partial = True

    status = "Partial" if partial else "Supported"
    return (status, " ".join(notes) if notes else "-1 to hit when targeted.")


def _melee_damage_bonus_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time (?:this model|a model in this unit) makes a melee attack that targets a monster or vehicle unit"
        r"(?: until the end of the phase)? "
        r"(?:add (?P<val>\d+) to the damage characteristic of that attack|improve the damage characteristic of that attack by (?P<val2>\d+))"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    val = m.group("val") or m.group("val2")
    return ("Supported", f"Melee attacks vs MONSTER/VEHICLE get +{val} Damage.")


def _melee_charge_strength_damage_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time a model in (?:this|that) unit makes (?:a|an)? melee attack(?:s)? "
        r"if (?:this|that) unit made a charge move this turn "
        r"improve the strength and damage characteristic(?:s)? of that attack by (?P<val>\d+)"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    val = m.group("val")
    return ("Supported", f"Melee attacks after charging: +{val} Strength and +{val} Damage.")


def _end_of_fight_embark_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the end of the fight phase if there are no models currently embarked within this transport you can select one friendly "
        r"(?P<keyword>[a-z0-9 ]+) infantry unit "
        r"(?:that only includes models from the units listed in this (?:unit s|units) transport section )?"
        r"(?:that )?has (?P<max>\d+) or fewer models "
        r"(?:and )?that is wholly within (?P<range>\d+) of this transport "
        r"(?:you cannot select a unit that can fly )?"
        r"unless that unit is within engagement range of one or more enemy units it can embark within this transport"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    keyword = (m.group("keyword") or "friendly").strip().upper()
    max_models = m.group("max") or ""
    range_val = m.group("range") or ""
    notes = [f"End of Fight phase: empty transport can embark friendly {keyword} INFANTRY"]
    if max_models:
        notes.append(f"<= {max_models} models")
    if range_val:
        notes.append(f"wholly within {range_val}\"")
    if "cannot select a unit that can fly" in norm:
        notes.append("(no FLY)")
    notes.append("if not within Engagement Range.")
    return ("Supported", " ".join(notes))


def _transport_disembark_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    notes: List[str] = []
    normal_move = r".*disembark.*after it has made a normal move.*(?:eligible to declare a charge|can declare a charge).*"
    after_advance = r".*disembark.*after it has advanced.*cannot declare a charge.*"
    if re.fullmatch(normal_move, norm):
        notes.append("Disembark after Normal move and still eligible to charge.")
    if re.fullmatch(after_advance, norm):
        notes.append("Disembark after Advance; counts as Normal move; cannot charge.")
    if notes:
        return ("Supported", " ".join(notes))
    return None


def _transport_reactive_disembark_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your opponents movement phase each time an enemy unit is set up(?: on the battlefield)? "
        r"or ends a normal advance or fall back move within (?P<range>\d+) of this (?:model|unit) "
        r"any units embarked within it can disembark"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    rng = m.group("range")
    return ("Supported", f"Enemy unit set up/move within {rng}\": disembark embarked units.")


def _enemy_move_reactive_d6_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once per turn when an enemy unit ends a normal advance or fall back move within (?P<range>\d+) of this "
        r"(?:model(?: s)? unit|unit|model)(?: if this unit is not within engagement range of "
        r"(?:one or more|any) enemy units?)? (?:this unit |this model |it )?can make a normal move of up to (?P<move>d6|\d+)"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    rng = m.group("range")
    move = str(m.group("move") or "").strip().lower()
    move_label = "D6" if move == "d6" else move
    note = f"Enemy unit ends move within {rng}\": optional {move_label}\" Normal move"
    if "not within engagement range" in norm:
        note += " if not in Engagement Range."
    else:
        note += "."
    return ("Supported", note)


def _horde_move_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm or "horde move" not in norm:
        return None
    if not re.search(r"each time an enemy unit has shot", norm):
        return None
    if not re.search(
        r"if (?:one or more|any) models from this unit were destroyed as a result of those attacks",
        norm,
    ):
        return None
    if not re.search(r"roll (?:one|a|1)? d6", norm):
        return None
    if "as close as possible to the closest enemy unit" not in norm:
        return None
    if "excluding aircraft" not in norm:
        return None
    if "within engagement range" not in norm:
        return None
    if "battle shocked" not in norm:
        return None
    note = (
        "Reactive Horde Move after enemy shooting casualties: D6\" move must end closest enemy unit "
        "(excluding AIRCRAFT) and can enter Engagement Range; blocked while Battle-shocked."
    )
    return ("Supported", note)


def _setup_reactive_shoot_or_charge_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the end of your opponents movement phase.*?"
        r"select one enemy unit that was set up on the battlefield within (?P<range>\d+) of this (?:model|unit).*?"
        r"can then either shoot at that unit but only if it is an eligible target.*?"
        r"declare a charge against that unit.*?"
        r"does not receive any charge bonus"
    )
    m = re.search(pattern, norm)
    if not m:
        return None
    rng = m.group("range")
    return (
        "Supported",
        f"End of opponent Movement phase: select enemy set up within {rng}\" to shoot (if eligible) or charge without charge bonus.",
    )


def _sticky_objective_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    legacy = (
        r"at the end of your command phase if this unit is within range of an objective marker you control "
        r"that objective marker remains under your control even if you have no models within range of it "
        r"until your opponent controls it"
    )
    legacy_timed = (
        r"at the end of your command phase if this unit is within range of an objective marker you control "
        r"that objective marker remains under your control even if you have no models within range of it "
        r"until your opponent controls it at (?:the )?start or end of any turn"
    )
    legacy_timed_control = (
        r"if you control an objective marker at the end of your command phase and this unit is within range of that objective marker "
        r"that objective marker remains under your control even if you have no models within range of it "
        r"until your opponent controls it at (?:the )?start or end of any turn"
    )
    loc = (
        r"at the end of your command phase if this unit is within range of an objective marker you control "
        r"that objective marker remains under your control until your opponents level of control over that "
        r"objective marker is greater than yours at the end of a phase"
    )
    loc_control = (
        r"at the end of your command phase if you control an objective marker that this unit "
        r"(?:or a transport it is embarked within )?is within range of that objective marker remains under your control "
        r"until your opponents level of control over that objective marker is greater than yours at the end of a phase"
    )
    if not (
        re.fullmatch(legacy, norm)
        or re.fullmatch(legacy_timed, norm)
        or re.fullmatch(legacy_timed_control, norm)
        or re.fullmatch(loc, norm)
        or re.fullmatch(loc_control, norm)
    ):
        return None
    return ("Supported", "End of Command phase: objective becomes sticky while you controlled it.")


def _command_phase_bodyguard_return_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"while this model is leading (?:a|this) unit in your command phase you can return (?:up to )?(one|a|\d+) destroyed bodyguard models? to that unit"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    token = m.group(1)
    try:
        amount = int(token)
    except Exception:
        amount = 1 if token in ("one", "a") else 0
    if amount <= 0:
        return None
    return (
        "Supported",
        f"Command phase: return {amount} destroyed Bodyguard model(s) while leading (capped at starting strength).",
    )


def _charge_phase_bodyguard_loss_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the end of your charge phase if this model is leading a unit and that unit is not within engagement range "
        r"of (?:one or more|any) enemy units? you must take a leadership test for this model if that test is failed "
        r"one bodyguard model in that unit is destroyed"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "End of Charge phase: if leading and not engaged, test Leadership; on fail, destroy 1 Bodyguard model.",
    )


def _opponent_turn_strategic_reserves_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"(?:once per battle(?:,)?\s+)?at the end of your opponents turn if this unit is not within engagement range of one or more enemy units "
        r"you can remove it from the battlefield and place it into strategic reserves"
    )
    if not re.fullmatch(pattern, norm):
        return None
    note = "End of opponent's turn: if not in Engagement Range, may enter Strategic Reserves."
    if "once per battle" in norm:
        note = f"{note} Once per battle."
    return ("Supported", note)


def _strategic_reserves_early_arrival_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"if this unit starts the game in strategic reserves it can be set up in the reinforcements step of your first "
        r"second or third movement phase(?: regardless of any mission rules)? if this unit is in strategic reserves "
        r"for the purposes of setting up this unit on the battlefield treat the (?:current )?battle round number "
        r"as being one higher than it actually is"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "Strategic Reserves: may arrive in battle rounds 1-3; treat battle round as +1 when setting up.",
    )


def _opponent_turn_destroyed_reposition_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once in each of your opponents turns if this model is on the battlefield when (?:another )?friendly (?P<keyword>[a-z0-9 ]+) unit is destroyed "
        r"just after removing the last model in that unit you can remove this model from the battlefield and set it up as close as possible "
        r"to where that destroyed model was destroyed and not within engagement range of (?:one or more|any) enemy units?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    keyword = (m.group("keyword") or "friendly").strip().upper()
    return (
        "Supported",
        f"Opponent's turn: after another friendly {keyword} unit is destroyed, this model can reposition as close as possible outside Engagement Range (once per opponent turn).",
    )


def _enemy_fall_back_desperate_escape_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    base = (
        r"each time an enemy unit(?: excluding monsters and vehicles)?(?: that is)? within engagement range of "
        r"(?:this unit|this model s unit|one or more units from your army with this ability) "
        r"(?:falls back|is selected to fall back) "
        r"(?:all )?(?:models in that enemy unit|that unit) must take (?:a )?desperate escape tests?"
    )
    penalty_clause = (
        r"(?: (?:when doing so )?if that enemy unit is (?:also )?battle shocked subtract (?P<pen>\d+) from "
        r"(?:each of those desperate escape tests|each of those tests|that test))?"
    )
    m = re.fullmatch(base + penalty_clause, norm)
    if not m:
        return None
    exclude = "excluding monsters and vehicles" in norm
    penalty = m.group("pen") if m.groupdict().get("pen") else None
    notes = []
    if exclude:
        notes.append("Enemy non-MONSTER/VEHICLE units within Engagement Range that Fall Back take Desperate Escape tests.")
    else:
        notes.append("Enemy units within Engagement Range that Fall Back take Desperate Escape tests.")
    if penalty:
        notes.append(f"Battle-shocked targets suffer -{penalty} to those tests.")
    return ("Supported", " ".join(notes))


def _command_phase_bonus_cp_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"(?:at the )?start of (?:each of )?your command phases? if (?:this model|this unit|the bearer) is on the battlefield "
        r"you gain (?P<cp>\d+) ?(?:cp|command points?)"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    return ("Supported", f"Start of Command phase: gain {m.group('cp')} CP while on the battlefield.")


def _phase_end_leadership_cp_gain_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the end of your shooting phase or the fight phase if "
        r"(?:the bearers unit|the bearer s unit|this unit|this models unit|this model s unit) destroyed one or more enemy units? that phase "
        r"(?:the bearers unit|the bearer s unit|this unit|this models unit|this model s unit) takes a leadership test "
        r"if that test is passed you gain (?P<cp>\d+|one) ?(?:cp|command points?)"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    cp_token = str(m.group("cp") or "")
    cp_label = "1" if cp_token == "one" else cp_token
    return (
        "Supported",
        f"End of Shooting/Fight phase: if bearer unit destroyed enemy units, pass Leadership test to gain {cp_label} CP.",
    )


def _command_phase_regain_wound_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"(?:at the )?start of (?:each of )?your command phases? "
        r"this model regains (?P<amt>\d+) lost wounds?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    return ("Supported", f"Start of Command phase: this model regains {m.group('amt')} lost wound(s).")


def _start_shooting_phase_visible_battleshock_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the start of your shooting phase select one enemy unit within (?P<range>\d+) (?:of )?and visible to this model "
        r"that enemy unit must take a battle shock test"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    return (
        "Supported",
        f"Start of Shooting phase: select a visible enemy unit within {m.group('range')}\" to take a Battle-shock test.",
    )


def _post_shoot_battleshock_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase after this (?:model|unit) has shot select one enemy "
        r"(?:(?P<infantry>infantry) )?unit (?:that was )?hit by one or more of those attacks "
        r"that (?:enemy )?unit must take a battle shock test"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    if m.group("infantry"):
        return ("Supported", "After shooting, pick a hit enemy INFANTRY unit to take a Battle-shock test.")
    return ("Supported", "After shooting, pick a hit enemy unit to take a Battle-shock test.")


def _post_shoot_shoot_again_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = r"once per battle in your shooting phase after this (?:unit|model) has shot it can shoot again"
    if not re.fullmatch(pattern, norm):
        return None
    return ("Supported", "Once per battle (after shooting): this unit can shoot again.")


def _post_shoot_infantry_mortal_wounds_battleshock_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase after this models unit has shot select one enemy infantry unit hit by one or more of those attacks "
        r"and roll (?:three|3) d6 for each 4 that enemy unit suffers 1 mortal wounds? "
        r"if an enemy unit suffers one or more mortal wounds as a result of this ability it must take a battle shock test"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "After shooting: pick a hit enemy INFANTRY unit; roll 3D6 (4+ -> 1 mortal wound). If any mortals are inflicted, it takes a Battle-shock test.",
    )


def _post_shoot_wracking_agonies_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase after this model has shot select one infantry unit hit by one or more of those attacks "
        r"made with its agonising energies until the start of your next turn that unit is wracked with agonies "
        r"while a unit is wracked with agonies subtract 2 from its move characteristic and subtract 2 from charge rolls made for it"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "After shooting: pick a hit enemy INFANTRY unit hit by Agonising Energies; until your next turn, it suffers -2\" Move and -2 to Charge rolls.",
    )


def _post_shoot_suppression_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase after this (?:model|unit) has shot select one enemy unit hit by one or more of those attacks "
        r"(?:excluding monsters and vehicles )?until the start of your next turn that enemy unit is suppressed "
        r"while a unit is suppressed each time a model in that unit makes an attack subtract 1 from the hit roll"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    if "excluding monsters and vehicles" in norm:
        return ("Supported", "After shooting, suppress a hit enemy unit (not MONSTER/VEHICLE) for -1 to hit until your next turn.")
    return ("Supported", "After shooting, suppress a hit enemy unit for -1 to hit until your next turn.")


def _post_shoot_no_cover_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase after this unit has shot select one enemy unit hit by one or more of those attacks made with "
        r"(?:a|an|the) (?P<weapon>[a-z0-9 ]+) until the end of the phase that enemy unit cannot have the benefit of cover"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    weapon = (m.group("weapon") or "weapon").strip()
    return ("Supported", f"After shooting: select a hit enemy unit hit by {weapon}; it cannot gain Benefit of Cover until phase end.")


def _post_shoot_snare_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase after this model has shot select one enemy unit hit by one or more of those attacks made with "
        r"(?:a|an|the|its) (?P<weapon>[a-z0-9 ]+) until the start of your next turn that enemy unit is snared "
        r"while a unit is snared each time that unit makes a normal advance or fall back move roll (?:one|1) d6 for each model in that unit "
        r"for each 1 that unit suffers 1 mortal wounds?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    weapon = (m.group("weapon") or "weapon").strip()
    return (
        "Supported",
        f"After shooting: select a hit enemy unit hit by {weapon}; it is snared until your next turn and suffers mortals on Normal/Advance/Fall Back moves.",
    )


def _post_shoot_leadership_debuff_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase after this unit has shot select one enemy unit hit by one or more of those attacks "
        r"until the start of your next shooting phase each time a battle shock or leadership test is taken for that "
        r"(?:enemy )?unit subtract 1 from that test"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "After shooting, pick a hit enemy unit; until your next Shooting phase, it suffers -1 to Battle-shock/Leadership tests.",
    )


def _aura_battleshock_leadership_penalty_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    if "enemy unit" not in norm or "battle shock" not in norm or "test" not in norm:
        return None
    m_range = re.search(r"within (?P<range>\d+)", norm)
    m_val = re.search(r"subtract (?P<val>\d+) from", norm)
    if not m_range or not m_val:
        return None
    try:
        rng = int(m_range.group("range"))
        val = int(m_val.group("val"))
    except Exception:
        return None
    if rng <= 0 or val <= 0:
        return None
    if "leadership" in norm:
        note = f"Aura: enemy units within {rng}\" suffer -{val} to Battle-shock/Leadership tests."
    else:
        note = f"Aura: enemy units within {rng}\" suffer -{val} to Battle-shock tests."
    return ("Supported", note)


def _crewed_platform_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"when the last (guardian defender|storm guardian) model in this unit is destroyed "
        r"any remaining (heavy weapon platform|serpent s scale platform|serpents scale platform) models in this unit are also destroyed"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    crew = m.group(1)
    platform = m.group(2)
    crew_label = "Guardian Defender" if crew == "guardian defender" else "Storm Guardian"
    platform_label = "Heavy Weapon Platform" if "heavy weapon" in platform else "Serpent's Scale Platform"
    return ("Supported", f"When the last {crew_label} model is destroyed, remaining {platform_label} models in the unit are destroyed.")


def _fight_phase_engagement_battleshock_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern_model = (
        r"(?:at the )?start of the fight phase each enemy unit within engagement range of this model must take a battle shock test"
        r"(?: subtracting (?P<penalty>\d+) from (?:that test|the result) if that enemy unit is below half strength)?"
    )
    pattern_unit = (
        r"(?:at the )?start of the fight phase each enemy unit within engagement range of one or more units (?:from your army )?"
        r"with this ability must take a battle shock test"
        r"(?: subtracting (?P<penalty>\d+) from the result if that enemy unit is below half strength)?"
    )
    m = re.fullmatch(pattern_model, norm)
    if not m:
        m = re.fullmatch(pattern_unit, norm)
    if not m:
        return None
    if m.group("penalty"):
        return (
            "Supported",
            f"Start of Fight phase: each enemy unit in Engagement Range takes a Battle-shock test; Below Half-strength suffers -{m.group('penalty')}.",
        )
    return ("Supported", "Start of Fight phase: each enemy unit in Engagement Range takes a Battle-shock test.")


def _fight_phase_aura_battleshock_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the start of the fight phase (?:each|every) enemy unit"
        r"(?: excluding (?P<exclude>[a-z0-9 ]+?))? within (?P<range>\d+) of this model must take a battle shock test"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    try:
        rng = int(m.group("range") or 0)
    except Exception:
        rng = 0
    if rng <= 0:
        return None
    note = f"Start of Fight phase: enemy units within {rng}\" take a Battle-shock test."
    exclude_raw = str(m.group("exclude") or "").strip()
    if exclude_raw:
        tokens = []
        for token in re.split(r"\band\b|,", exclude_raw):
            t = str(token or "").strip().upper()
            if t:
                tokens.append(t)
        if tokens:
            note = f"Start of Fight phase: enemy units within {rng}\" (excluding {', '.join(tokens)}) take a Battle-shock test."
    return ("Supported", note)


def _charge_end_engagement_battleshock_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time this model s unit ends a charge move each enemy unit within engagement range of that unit must take a battle shock test"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return ("Supported", "After this unit ends a Charge move, engaged enemy units take Battle-shock tests.")


def _start_any_phase_battleshock_clear_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once per battle at the start of any phase you can select one friendly (?P<keyword>[a-z0-9 ]+?) unit that is battle shocked "
        r"and within (?P<range>\d+) of (?:this model|the bearer|this unit s (?P<model>[a-z0-9 ]+?) model) that unit is no longer battle shocked"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    try:
        rng = int(m.group("range") or 0)
    except Exception:
        rng = 0
    if rng <= 0:
        return None
    keyword = str(m.group("keyword") or "").strip()
    keyword_label = keyword.upper() if keyword else "friendly"
    note = f"Once per battle, start of any phase: clear Battle-shock on a {keyword_label} unit within {rng}\"."
    return ("Supported", note)


def _fight_phase_below_starting_strength_fight_first_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the start of the fight phase if this model\s*s unit is below its starting strength until the end of the phase "
        r"models in that unit have the fights first ability"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "Start of Fight phase: if the unit is below Starting Strength, it gains Fights First until end of phase.",
    )


def _fight_phase_end_mortal_wounds_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the end of the fight phase you can select one enemy unit within engagement range of this model "
        r"and roll (?:eight|8) d6 for each 4 that enemy unit suffers 1 mortal wounds?"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return ("Supported", "End of Fight phase: pick an engaged enemy; roll 8D6, each 4+ inflicts 1 mortal wound.")


def _fight_phase_once_melee_attacks_ap_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once per battle at the start of the fight phase this model can use this ability if it does until the end of the phase "
        r"add 3 to the attacks characteristic of melee weapons equipped by this model and improve the armou?r penetration "
        r"characteristic of those weapons by 1"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return ("Supported", "Once per battle (start of Fight phase): +3 Attacks and +1 AP for bearer melee weapons.")


def _start_any_phase_damage_set_one_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once per battle at the start of any phase this model can use this ability if it does until the end of the phase "
        r"each time an attack is allocated to this model change the damage characteristic of that attack to 1"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "Once per battle (start of any phase): allocated attacks against this model have Damage 1 until end of phase.",
    )


def _start_any_phase_unit_fnp_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once per battle at the start of any phase this unit can use this ability if it does until the end of the phase "
        r"models in this unit have the feel no pain (?P<val>[1-6])(?: ability)?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    return (
        "Supported",
        f"Once per battle (start of any phase): unit gains Feel No Pain {m.group('val')}+ until end of phase.",
    )


def _dark_ritual_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once per battle in your command phase if this unit contains a cult demagogue model it can use this ability "
        r"if it does until the end of (?:the|that) turn this unit can declare a charge in a turn in which it advanced "
        r"and each time a model in this unit makes an attack add 1 to the hit roll and add 1 to the wound roll"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "Once per battle (Command phase): unit can charge after Advancing and gains +1 to hit and wound until end of turn.",
    )


def _movement_phase_once_normal_move_weapon_attacks_bonus_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once per battle (?:in|during) your movement phase before this model makes (?:a )?normal move it can use this ability "
        r"if it does until the end of the turn add (?P<move>\d+d\d+) to this models move characteristic "
        r"and add (?P<attacks>\d+) to the attacks characteristic of this models (?P<weapon>[a-z0-9 ]+? weapon(?:s)?)"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    move = str(m.group("move") or "").upper()
    attacks = m.group("attacks") or ""
    weapon = m.group("weapon") or "weapon"
    return (
        "Supported",
        f"Once per battle (before Normal move): add {move} Move and +{attacks} Attacks to {weapon}.",
    )


def _movement_phase_normal_move_speed_mortal_wounds_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your movement phase each time this unit is selected to make (?:a )?normal move it can use this ability "
        r"if it does until the end of the turn this unit is not eligible to declare a charge and models in it have a move characteristic of (?P<move>\d+) "
        r"each time this unit uses this ability at the end of the phase roll (?:one|1) d6 for each model in this unit for each 1 "
        r"this unit suffers 1 mortal wounds?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    move = m.group("move") or "24"
    return (
        "Supported",
        f"Movement phase (Normal move): optional; set Move to {move}\", cannot charge; end of phase roll D6 per model, each 1 causes 1 mortal wound.",
    )


def _movement_phase_end_visible_wound_bonus_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the end of your movement phase select one enemy unit within (?P<range>\d+) of and visible to this model "
        r"until the start of your next command phase each time a friendly (?P<keyword>[a-z0-9 ]+) models? make(?:s)? an attack that targets that enemy unit "
        r"add (?P<bonus>\d+) to the wound rolls?(?: each unit can only be selected for this ability once per turn)?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    range_val = m.group("range") or "18"
    keyword = (m.group("keyword") or "friendly").strip().upper()
    bonus = m.group("bonus") or "1"
    return (
        "Supported",
        f"End of Movement phase: select visible enemy within {range_val}\"; friendly {keyword} models gain +{bonus} to wound vs that target until next Command phase.",
    )


def _movement_phase_end_visible_hit_bonus_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the end of your movement phase select one enemy unit within (?P<range>\d+) of and visible to this model "
        r"until the start of your next command phase each time a friendly (?P<keyword>[a-z0-9 ]+) models? make(?:s)? an attack that targets that enemy unit "
        r"add (?P<bonus>\d+) to the hit rolls?(?: each unit can only be selected for this ability once per turn)?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    range_val = m.group("range") or "18"
    keyword = (m.group("keyword") or "friendly").strip().upper()
    bonus = m.group("bonus") or "1"
    return (
        "Supported",
        f"End of Movement phase: select visible enemy within {range_val}\"; friendly {keyword} models gain +{bonus} to hit vs that target until next Command phase.",
    )


def _movement_phase_end_enemy_within_range_mortal_table_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the end of your movement phase roll (?:one|1) d6 for each enemy unit within (?P<range>\d+) of this model "
        r"on a 2 3 that unit suffers 1 mortal wounds? on a 4 5 that unit suffers d3 mortal wounds? on a 6 that unit suffers d6 mortal wounds?"
        r"(?: each enemy unit within range of this ability must then take a battle shock test)?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    range_val = m.group("range") or "6"
    battle_shock = "battle shock test" in norm
    note = (
        f"End of Movement phase: roll D6 for each enemy within {range_val}\"; "
        "2-3=1 mortal wound, 4-5=D3, 6=D6."
    )
    if battle_shock:
        note = f"{note} Units within range take Battle-shock tests after resolving mortals."
    return ("Supported", note)


def _movement_phase_end_enemy_within_range_mortal_threshold_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the end of your movement phase roll (?:one|1) d6 for each enemy unit within (?P<range>\d+) of one or more models with this ability "
        r"on a (?P<threshold>\d)\+? that enemy unit suffers (?P<mw>d3|d6|\d+) mortal wounds?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    range_val = m.group("range") or "9"
    threshold = m.group("threshold") or "3"
    mw = (m.group("mw") or "d3").upper()
    return (
        "Supported",
        f"End of Movement phase: roll D6 for each enemy within {range_val}\" of models with this ability; on a {threshold}+ it suffers {mw} mortal wounds.",
    )


def _grenade_pack_flyover_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once per turn in your movement phase when this unit is set up on the battlefield or ends a normal advance or fall back move "
        r"it can use this ability if it does select one enemy unit within (?P<range>\d+) of and visible to this unit "
        r"and roll one d6 for each (?P<models>[a-z0-9 ]+) model in this unit "
        r"for each (?P<threshold>\d)\+? that enemy unit suffers (?P<mw>\d+) mortal wounds? "
        r"(?:to a maximum of (?P<cap>\d+) mortal wounds?)? "
        r"each time this unit uses this ability until the end of the turn you cannot target this unit with the grenade stratagem"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    range_val = m.group("range") or "8"
    threshold = m.group("threshold") or "4"
    cap = m.group("cap") or ""
    cap_note = f" (max {cap})" if cap else ""
    return (
        "Supported",
        f"Movement phase (once per turn): select visible enemy within {range_val}\"; roll D6 per model, each {threshold}+ inflicts 1 mortal wound{cap_note}; cannot be targeted by Grenade stratagem that turn.",
    )


def _daemonic_patrons_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time this unit is selected to fight it can call upon (?:the )?daemonic patrons if it does until the end of the phase "
        r"each time a model in this unit makes an attack an unmodified wound roll of (?P<thresh>\d) scores a critical wound "
        r"at the end of the fight phase if this unit called upon (?:the )?daemonic patrons this phase and no enemy models were destroyed "
        r"by attacks made by models in this unit this phase one model in this unit is destroyed"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    thresh = m.group("thresh") or "3"
    return (
        "Supported",
        f"Fight phase (selected to fight): optional critical wound on {thresh}+; end of phase, if no enemy models destroyed, destroy 1 model.",
    )


def _return_on_death_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"the first time (?:this model|the bearer) is destroyed(?: remove it from play without resolving its deadly demise ability)?(?: then)? "
        r"(?:at the end of the phase roll one d6|roll one d6 at the end of the phase) on a (?P<roll>\d+) "
        r"set (?:this model|the bearer) back up on the battlefield(?: as close as possible to where it was destroyed)? "
        r"and not within engagement range of (?:one or more|any) enemy (?:units|models) with "
        r"(?P<wounds>its full wounds remaining|(?:d3|d6|\d+) wounds? remaining)"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    roll = m.group("roll") or "2"
    wounds_raw = m.group("wounds") or ""
    wounds_desc = "full wounds"
    if "full wounds" in wounds_raw:
        wounds_desc = "full wounds"
    elif wounds_raw.startswith("d3"):
        wounds_desc = "D3 wounds"
    elif wounds_raw.startswith("d6"):
        wounds_desc = "D6 wounds"
    else:
        m2 = re.search(r"\d+", wounds_raw)
        if m2:
            wounds_desc = f"{m2.group(0)} wounds"
    return (
        "Supported",
        f"First time destroyed: roll D6 at end of phase; on {roll}+ return with {wounds_desc} (not within Engagement Range).",
    )


def _melee_fight_on_death_after_attacks_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"(?:each time |if )?(?:a model in this unit|this model) is destroyed by a melee attack if (?:that model|it) has not fought this phase "
        r"roll one d6 on a (?P<threshold>\d+) do not remove (?:it|this model|that destroyed model) from play "
        r"(?:that destroyed model|this model) can fight after the attacking (?:unit|model s unit) has finished making its attacks "
        r"and is then removed from play"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    threshold = m.group("threshold") or "3"
    return (
        "Supported",
        f"Melee fight-on-death: roll D6 on destruction; on {threshold}+ fight after the attacker finishes its attacks.",
    )


def _conditional_lone_operative_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"while this model is within (?P<rng>\d+) of one or more (?:other )?friendly "
        r"(?P<keywords>.+?) units (?:this model|it) has (?:the )?lone operative ability"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    keywords = m.group("keywords") or ""
    if " or " in keywords or " excluding " in keywords:
        return None
    rng = m.group("rng") or "3"
    return (
        "Supported",
        f"Conditional Lone Operative within {rng}\" of friendly {keywords.upper()} units.",
    )


def _charge_target_strength_bonus_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time this (?:model|unit) declares a charge that targets? one or more units? (?:that are )?below starting strength "
        r"add (?P<base>\d+) to the charge roll if one or more of the targets? of that charge are below half strength "
        r"add (?P<half>\d+) to the charge roll instead"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    return (
        "Supported",
        f"Charge roll bonus vs reduced strength targets: +{m.group('base')} if any target is Below Starting Strength; "
        f"+{m.group('half')} instead if any target is Below Half-strength.",
    )


def _daemonic_allegiance_wargear_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    header = [
        "when",
        "you",
        "select",
        "this",
        "model",
        "to",
        "include",
        "in",
        "your",
        "army",
        "you",
        "must",
        "select",
        "one",
        "of",
        "the",
        "keywords",
        "below",
        "until",
        "the",
        "end",
        "of",
        "the",
        "battle",
        "this",
        "model",
        "has",
        "that",
        "keyword",
        "and",
        "the",
        "additional",
        "wargear",
        "stated",
        "for",
        "that",
        "keyword",
        "below",
    ]
    tokens = norm.split()
    if tokens[:len(header)] != header:
        return None
    idx = len(header)
    if idx >= len(tokens):
        return None
    keywords = {"khorne", "tzeentch", "nurgle", "slaanesh"}
    effect = ["this", "model", "is", "additionally", "equipped", "with"]
    options: list[tuple[str, str]] = []
    seen = set()
    while idx < len(tokens):
        kw = tokens[idx]
        if kw not in keywords:
            return None
        idx += 1
        if tokens[idx:idx + len(effect)] != effect:
            return None
        idx += len(effect)
        start = idx
        while idx < len(tokens) and tokens[idx] not in keywords:
            idx += 1
        if start == idx:
            return None
        wargear = " ".join(tokens[start:idx]).strip()
        if not wargear:
            return None
        if kw in seen:
            return None
        seen.add(kw)
        options.append((kw, wargear))
    if not options:
        return None
    return ("Supported", "Selects one god keyword at muster and adds the matching wargear to the model.")


def _reinforcements_denial_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"enemy units that are set up (?:on the battlefield )?(?:as reinforcement(?:s)?|from reserve(?:s)?) cannot be set up within "
        r"(?P<dist>\d+(?:\.\d+)?) (?:horizontally )?of this (?:model|unit)"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    horiz = "horizontally" in norm
    horiz_note = " horizontally" if horiz else ""
    return ("Supported", f"Reinforcements cannot be set up within {m.group('dist')}\"{horiz_note} of this model/unit.")


def _gain_cp_on_destroy_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time (?:this model|this unit|this models unit) destroys an? (?:enemy )?(?:character|epic hero|monster|vehicle|psyker)? ?"
        r"(?:model|unit)? you gain (?P<cp>\d+) ?cp"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    cp = m.group("cp")

    keyword_map = {
        "character": "CHARACTER",
        "epic hero": "EPIC HERO",
        "monster": "MONSTER",
        "vehicle": "VEHICLE",
        "psyker": "PSYKER",
    }
    target_keywords = [kw for needle, kw in keyword_map.items() if needle in norm]
    kw_text = ""
    if target_keywords:
        if len(target_keywords) > 1 and " or " in norm:
            kw_text = " or ".join(target_keywords)
        else:
            kw_text = " ".join(target_keywords)

    trigger = "target"
    if "model" in norm:
        trigger = "model"
    elif "unit" in norm:
        trigger = "unit"

    subject = "this model" if "this model" in norm else "this unit"

    if kw_text:
        if trigger in ("model", "unit"):
            target_text = f"enemy {kw_text} {trigger}"
        else:
            target_text = f"enemy {kw_text} target"
    else:
        target_text = f"enemy {trigger}" if trigger in ("model", "unit") else "enemy unit/model"

    return ("Supported", f"Gain {cp} CP when {subject} destroys an {target_text}.")


def _fall_back_shoot_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    base = r"this unit is eligible to shoot in a turn in which it (?:advanced or )?(?:fell back|fall back)"
    charge = r"this unit is eligible to shoot and (?:declare a charge|charge) in a turn in which it (?:advanced or )?(?:fell back|fall back)"
    if not (re.fullmatch(base, norm) or re.fullmatch(charge, norm)):
        return None
    has_advance = "advanced or" in norm
    has_charge = "declare a charge" in norm or "shoot and charge" in norm
    notes = []
    if has_advance:
        notes.append("Shoot-after-Advance/Fall Back eligibility.")
    else:
        notes.append("Shoot-after-Fall-Back eligibility.")
    if has_charge:
        if has_advance:
            notes.append("Charge-after-Advance/Fall Back eligibility.")
        else:
            notes.append("Charge-after-Fall-Back eligibility.")
    return ("Supported", " ".join(notes))


def _advance_no_roll_fixed_distance_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"(?:while this model is leading a unit )?"
        r"each time (?:this unit|this model|this models unit|this model s unit|that unit) advances "
        r"do not make an advance roll(?: for it)? "
        r"instead until the end of the phase add (?P<dist>\d+) to the move characteristic "
        r"(?:of (?:models in )?)?(?:this unit|this model|this models unit|that unit)"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    try:
        dist = int(m.group("dist"))
    except Exception:
        dist = 0
    if dist <= 0:
        return None
    return ("Supported", f"Advance: fixed +{dist}\" Move instead of rolling.")


def _movement_ignore_vertical_distance_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    if "ignore" not in norm or "vertical distance" not in norm:
        return None
    if "each time" not in norm or "move" not in norm:
        return None
    move_types = []
    if "normal" in norm:
        move_types.append("Normal")
    if "advance" in norm:
        move_types.append("Advance")
    if "fall back" in norm:
        move_types.append("Fall Back")
    if "charge" in norm:
        move_types.append("Charge")
    if not move_types:
        return None
    note = f"Ignore vertical distance during {', '.join(move_types)} moves."
    return ("Supported", note)


def _charge_move_devastating_wounds_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    model_patterns = (
        r"each time this model makes a charge move until the end of the turn its melee weapons have the devastating wounds ability",
        r"each time this model makes a charge move until the end of the turn melee weapons equipped by this model have the devastating wounds ability",
        r"each time this model makes a charge move until the end of the turn melee weapons it is equipped with have the devastating wounds ability",
    )
    unit_patterns = (
        r"each time this unit makes a charge move until the end of the turn melee weapons equipped by models in this unit have the devastating wounds ability",
        r"each time this models unit makes a charge move until the end of the turn melee weapons equipped by models in that unit have the devastating wounds ability",
        r"each time this unit makes a charge move until the end of the turn its melee weapons have the devastating wounds ability",
    )
    for pattern in model_patterns:
        if re.fullmatch(pattern, norm):
            return ("Supported", "On charge: model melee weapons gain Devastating Wounds until end of turn.")
    for pattern in unit_patterns:
        if re.fullmatch(pattern, norm):
            return ("Supported", "On charge: unit melee weapons gain Devastating Wounds until end of turn.")
    return None


def _defensive_charge_roll_penalty_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time an enemy unit declares a charge if one or more units with this ability are selected as a target of "
        r"that charge subtract (?P<val>\d+) from the charge roll"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    try:
        val = int(m.group("val"))
    except Exception:
        val = 0
    if val <= 0:
        return None
    return ("Supported", f"Enemy charges targeting this unit suffer -{val} to the Charge roll.")


def _leading_unit_phase_move_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"while this model is leading a unit models in that unit have the deep strike ability "
        r"and each time a model in that unit makes a normal advance fall back or charge move "
        r"it can move horizontally through models and terrain features "
        r"when making a normal advance or fall back move models in that unit can move within engagement range "
        r"of enemy models but cannot end that move within engagement range of them and any desperate escape test"
        r"(?:s)? (?:is|are) automatically passed"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "Leading: unit gains Deep Strike and phase-through movement (Normal/Advance/Fall Back/Charge); auto-pass Desperate Escape tests.",
    )


def _leading_unit_move_and_phase_terrain_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"while this model is leading a unit models in that unit have a move characteristic of (?P<move>\d+) "
        r"and each time a model in that unit makes a normal advance fall back or charge move "
        r"it can move horizontally through terrain features"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    return (
        "Supported",
        f"Leading: unit Move set to {m.group('move')}\" and can move horizontally through terrain (Normal/Advance/Fall Back/Charge).",
    )


def _move_over_friendly_monster_vehicle_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time (?:this model|this unit) makes a (?P<moves>.+?) move "
        r"it can move (?:over|through) friendly monster (?:and|or) vehicle models? and "
        r"(?:sections of )?terrain features that are (?P<height>\d+) or less in height"
        r"(?: as if they were not there)?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    moves_text = (m.group("moves") or "").strip()
    tokens = [t for t in moves_text.split() if t]
    allowed = {"normal", "advance", "fall", "back", "fallback", "or", "and"}
    if not tokens or any(t not in allowed for t in tokens):
        return None
    if "normal" not in tokens:
        return None
    move_types = ["Normal"]
    if "advance" in tokens:
        move_types.append("Advance")
    if "fallback" in tokens or "fall back" in moves_text:
        move_types.append("Fall Back")
    if not move_types:
        return None
    height = m.group("height")
    type_label = "/".join(move_types)
    return ("Supported", f"{type_label}: move through friendly MONSTER/VEHICLE models and terrain <= {height}\".")


def _move_over_low_terrain_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time (?:this model|this unit) makes a (?P<moves>.+?) move "
        r"it can move (?:over|through) (?:sections of )?terrain features that are (?P<height>\d+) or less in height"
        r"(?: as if they were not there)?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    moves_text = (m.group("moves") or "").strip()
    tokens = [t for t in moves_text.split() if t]
    allowed = {"normal", "advance", "fall", "back", "fallback", "or", "and"}
    if not tokens or any(t not in allowed for t in tokens):
        return None
    if "normal" not in tokens:
        return None
    move_types = ["Normal"]
    if "advance" in tokens:
        move_types.append("Advance")
    if "fallback" in tokens or "fall back" in moves_text:
        move_types.append("Fall Back")
    if not move_types:
        return None
    height = m.group("height")
    type_label = "/".join(move_types)
    return ("Supported", f"{type_label}: move over terrain features <= {height}\".")


def _titanic_move_through_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    agility_pattern = (
        r"each time this model makes a normal advance or fall back move it can move through models and terrain features "
        r"when doing so it can move within engagement range of enemy models but cannot end that move within engagement range of them"
    )
    strides_pattern = (
        r"each time this model makes a normal advance or fall back move it can move through models excluding titanic models "
        r"and sections of terrain features that are (?P<height>\d+) or less in height when doing so it can move within engagement range of enemy models "
        r"but cannot end that move within engagement range of them it can also move through sections of terrain features that are more than (?P=height) "
        r"in height but if it does after it has moved roll one d6 on a 1 this model is battle shocked"
    )
    if re.fullmatch(agility_pattern, norm):
        return (
            "Supported",
            "Normal/Advance/Fall Back: move through models and terrain; can move within Engagement Range but cannot end there.",
        )
    m = re.fullmatch(strides_pattern, norm)
    if not m:
        return None
    height = m.group("height") or "4"
    return (
        "Supported",
        f"Normal/Advance/Fall Back: move through models (excluding TITANIC) and terrain <= {height}\"; can move within Engagement Range but cannot end there. Crossing >{height}\" terrain risks Battle-shock on 1.",
    )


def _move_over_mortal_wounds_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"(?:once per battle(?:,)?\s+)?(?:(?:in|during) your movement phase(?:,)?\s+)?(?:each time|after) (?:this model|the bearer) ends a (?P<moves>[a-z ]+) move "
        r"(?:you can )?(?:select|choose) one enemy unit(?: excluding monsters and vehicles?(?: units)?)? "
        r"(?:that )?(?:it )?moved over during that move "
        r"(?:if you do )?(?:and |then )?roll (?P<dice>\d+|one|two|three|four|five|six|seven|eight|nine|ten) d6 "
        r"(?:adding (?P<fly_bonus>\d+) to each result if that enemy unit can fly )?"
        r"for each (?P<threshold>\d)\+? that (?:enemy )?unit suffers (?P<mw>d3|d6|\d+) mortal wounds?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        unit_pattern = (
            r"(?:once per battle(?:,)?\s+)?(?:(?:in|during) your movement phase(?:,)?\s+)?(?:each time|after) this unit ends a (?P<moves>[a-z ]+) move "
            r"(?:you can )?(?:select|choose) one enemy unit(?: excluding monsters and vehicles?(?: units)?)? "
            r"(?:that )?(?:it )?moved over during that move "
            r"(?:if you do )?(?:and |then )?roll (?:\d+|one|two|three|four|five|six|seven|eight|nine|ten) d6 for each model in this unit "
            r"(?:adding (?P<fly_bonus>\d+) to each result if that enemy unit can fly )?"
            r"for each (?P<threshold>\d)\+? that (?:enemy )?unit suffers (?P<mw>d3|d6|\d+) mortal wounds?"
        )
        m = re.fullmatch(unit_pattern, norm)
        if not m:
            return None
        moves_text = (m.group("moves") or "").strip()
        tokens = [t for t in moves_text.split() if t]
        allowed = {"normal", "advance", "or", "and"}
        if not tokens or any(t not in allowed for t in tokens):
            return None
        if "normal" not in tokens:
            return None
        move_types = ["Normal"]
        if "advance" in tokens:
            move_types.append("Advance")
        threshold = int(m.group("threshold") or 0)
        mw_token = str(m.group("mw") or "").strip().lower()
        if not mw_token or threshold <= 0:
            return None
        mortal_text = mw_token.upper()
        if not mw_token.startswith("d"):
            try:
                if int(mw_token) <= 0:
                    return None
            except Exception:
                return None
        type_label = "/".join(move_types)
        fly_bonus = int(m.group("fly_bonus") or 0) if m.group("fly_bonus") else 0
        fly_note = " (+{0} vs FLY)".format(fly_bonus) if fly_bonus else ""
        return (
            "Supported",
            f"{type_label}: select a moved-over enemy; roll D6 per model{fly_note}, each {threshold}+ inflicts {mortal_text} mortal wounds.",
        )
    moves_text = (m.group("moves") or "").strip()
    tokens = [t for t in moves_text.split() if t]
    allowed = {"normal", "advance", "or", "and"}
    if not tokens or any(t not in allowed for t in tokens):
        return None
    if "normal" not in tokens:
        return None
    move_types = ["Normal"]
    if "advance" in tokens:
        move_types.append("Advance")
    dice_raw = (m.group("dice") or "").strip().lower()
    dice_map = {
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
    }
    dice_count = int(dice_raw) if dice_raw.isdigit() else dice_map.get(dice_raw, 0)
    if dice_count <= 0:
        return None
    threshold = int(m.group("threshold") or 0)
    mw_token = str(m.group("mw") or "").strip().lower()
    if not mw_token:
        return None
    if threshold <= 0:
        return None
    mortal_text = mw_token.upper()
    if not mw_token.startswith("d"):
        try:
            if int(mw_token) <= 0:
                return None
        except Exception:
            return None
    type_label = "/".join(move_types)
    fly_bonus = int(m.group("fly_bonus") or 0) if m.group("fly_bonus") else 0
    fly_note = " (+{0} vs FLY)".format(fly_bonus) if fly_bonus else ""
    return (
        "Supported",
        f"{type_label}: select a moved-over enemy; roll {dice_count}D6{fly_note}, each {threshold}+ inflicts {mortal_text} mortal wounds.",
    )


def _battlesuit_support_system_support(name: str, description: str) -> Optional[Tuple[str, str]]:
    if _norm(name) != "battlesuit support system":
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    simple_patterns = (
        r"this unit is eligible to shoot in a turn in which it (?:fell back|fall back)",
        r"this model is eligible to shoot in a turn in which it (?:fell back|fall back)",
        r"the bearer is eligible to shoot in a turn in which it (?:fell back|fall back)",
        r"the bearers unit is eligible to shoot in a turn in which it (?:fell back|fall back)",
    )
    for pattern in simple_patterns:
        if re.fullmatch(pattern, norm):
            return ("Supported", "Shoot-after-Fall-Back eligibility.")
    if "only models equipped with this wargear can make ranged attacks" in norm:
        return ("Partial", "Shoot after Falling Back; wargear-only restriction not enforced.")
    if "loses the smoke keyword" in norm:
        return ("Partial", "Shoot after Falling Back; SMOKE loss not enforced.")
    return None


def _two_melee_weapons_bonus_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"if this model is equipped with two melee weapons in addition to its close combat weapon add (?P<amt>\d+) to the attacks characteristic of those two weapons",
        norm,
    )
    if not m:
        return None
    return (
        "Supported",
        f"If equipped with two melee weapons plus a close combat weapon, those two weapons gain +{m.group('amt')} Attacks.",
    )


def _attached_possessed_formation_bonus_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"if this model is attached to a world eaters possessed unit during the declare battle formations step until the end of the battle this model has the deep strike and scouts (?P<rng>\d+) abilities",
        norm,
    )
    if not m:
        return None
    return (
        "Supported",
        f"Leader gains Deep Strike and Scouts {m.group('rng')}\" if attached to WORLD EATERS POSSESSED at battle formations.",
    )


def _attached_battleline_infiltrators_scouts_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"if this model is attached to an? (?P<kw>.+?) battleline unit during the declare battle formations step "
        r"this model has the infiltrators and scouts (?P<rng>\d+) abilities",
        norm,
    )
    if not m:
        return None
    kw = (m.group("kw") or "").strip().upper()
    rng = m.group("rng") or "6"
    return (
        "Supported",
        f"Leader gains Infiltrators and Scouts {rng}\" if attached to friendly {kw} BATTLELINE at battle formations.",
    )


def _orders_section_support(name: str, description: str) -> Optional[Tuple[str, str]]:
    if _norm(name) != "orders":
        return None
    note = "Orders section parsed for Voice of Command (count, eligible keywords, and order limits)."
    if description:
        text = _strip_html(description)
        if text:
            return ("Supported", note)
    return ("Supported", note)


def _attached_unit_support(name: str, description: str) -> Optional[Tuple[str, str]]:
    if _norm(name) != "attached unit":
        return None
    note = "Attached Unit section parsed to extend leader attachment eligibility."
    text = _strip_html(description).lower()
    if "gains the" in text:
        return ("Partial", f"{note} Additional leader-gain effects not implemented.")
    return ("Supported", note)


def _enhancement_support(name: str, enh_id: str, description: str) -> Tuple[str, str]:
    explicit = {
        "000008432002": "Berzerker Glaive: +1A/+1D to bearer melee weapons (excluding Extra Attacks).",
        "000008432003": "Helm of Brazen Ire: reduce damage by 1 (min 1).",
        "000008432004": "Favoured of Khorne: Blessings rerolls while bearer on battlefield.",
        "000008432005": "Battle-lust: re-roll Charge; +1 Charge with Unbridled Bloodlust.",
        "000009899002": "Phoenix Gem: return on 2+ at end of phase after first destruction.",
        "000009899003": "Timeless Strategist: +1 Battle Focus token if bearer on battlefield.",
        "000009899004": "Gift of Foresight: Command Re-roll for 0CP once per battle round.",
        "000009899005": "Psychic Destroyer: +1 Damage to bearer ranged Psychic weapons.",
        "000009923005": "Torc of Morai-Heg: once per turn, opponent Stratagems targeting units within 12\" of the bearer cost +1CP.",
        "000009769002": "Guiding Presence: start of Shooting phase select friendly AELDARI VEHICLE within 9\" to gain +1 to hit until end of phase.",
        "000009769003": "Harmonisation Matrix: Command phase roll D6 if bearer/transport is within a controlled objective; on 3+, gain 1 CP.",
        "000009769004": "Spirit Stone of Raelyth: Lone Operative within 3\" of friendly AELDARI VEHICLE; Command phase select friendly AELDARI VEHICLE within 3\" to regain up to D3 lost wounds.",
        "000009769005": "Guileful Strategist: after deployment select up to three AELDARI VEHICLE units to redeploy; may place them into Strategic Reserves regardless of limits.",
        "000009927002": "Aspect of Murder: bearer melee weapons gain +1 Damage and [Precision].",
        "000009927003": "Mantle of Wisdom: while leading Aspect Warriors, unit gains both Path of the Warrior abilities when selected to shoot or fight.",
        "000009927004": "Shimmerstone: while leading Aspect Warriors, ranged attacks targeting the unit suffer -1 to wound.",
        "000009927005": "Strategic Savant: while leading Aspect Warriors, models in the unit gain +1 Objective Control.",
        "000008348005": "Adaptive Biology: bearer gains Feel No Pain 5+; at the start of any turn, if below starting wounds, upgrade to Feel No Pain 4+ for the rest of the battle.",
        "000010002002": "Faultless Opportunist: Heroic Intervention for 0CP even if another unit was targeted this phase.",
        "000010002005": "Rise to the Challenge: end of Fight phase (once per battle) fight one additional time and choose an Exquisite Swordsmanship ability.",
        "000010078002": "Icon of War: BLOOD LEGIONS within 6\" gain Blessings of Khorne; with Might of Khorne active, may re-roll Battle-shock tests.",
        "000010078003": "Blood-forged Armour: set bearer Save to 2+; gain 1 Blood Tithe point when bearer is destroyed.",
        "000010078004": "Disciple of Khorne: Lord on Juggernaut can attach to Bloodcrushers/Flesh Hounds; bearer gains Deep Strike and BLOOD LEGIONS (instead of WORLD EATERS) while leading; attached unit benefits from Blessings of Khorne (FAQ).",
        "000010078005": "Blade of Endless Bloodshed: +1 A/S/D for bearer melee weapons; melee kill auto-grants 1 Blood Tithe point.",
        "000010086002": "Murderous Onslaught: if bearer unit disembarked this turn, enemy units cannot use Fire Overwatch against it until end of turn.",
        "000010086003": "Aggressive Deployment: if bearer starts embarked in a Dedicated Transport, that Transport gains Scouts 9\".",
        "000010086004": "Unleash Hell: start of Shooting phase select a friendly Vehicle within 6\" (or bearer’s Transport); after it shoots, suppress a hit enemy unit until your next turn.",
        "000010086005": "Infernal Infusion: once per battle at the start of the Fight phase, bearer unit gains Fights First until end of phase.",
        "000010645002": "Carmine Reliquary: bearer unit gains Scouts 6\"; ADEPTUS ASTARTES within 6\" can re-roll Battle-shock tests.",
        "000010645003": "Master of the Red Thirst: once per battle start of Fight phase, bearer unit gains Fights First until end of phase.",
        "000010645004": "Sanguinary Tear (Aura): friendly Death Company within 6\" gain +1 Strength to weapons.",
        "000010645005": "Angel's Fang: bearer melee attacks vs CHARACTER/MONSTER/VEHICLE gain Sustained Hits 2.",
        "000009749002": "Dread Majesty (Aura): NECRONS units within 6\" (excluding TITANIC) re-roll Hit and Wound rolls of 1.",
        "000009749003": "Miniaturised Nebuloscope: bearer unit ranged weapons ignore cover.",
        "000009749004": "Demanding Leader: Command phase select friendly NECRONS VEHICLE/MOUNTED (non-TITANIC) within 6\" to shoot after Falling Back until next Command phase.",
        "000009749005": "Chrono-impedance Fields: Command phase select friendly NECRONS VEHICLE/MOUNTED (non-TITANIC) within 6\"; allocated damage -1 until next Command phase.",
        "000010123002": "Daemon Weapon of Nurgle: bearer melee attacks score critical hits on unmodified 5+.",
        "000010123003": "Furnace of Plagues: bearer melee weapons gain +1 Strength, +1 Attacks, and Devastating Wounds.",
        "000010123004": "Arch Contaminator: while the bearer's (attached) unit is within range of a controlled objective, attacks can re-roll Wound rolls.",
        "000010123005": "Revolting Regeneration: bearer gains Feel No Pain 5+.",
        "000009819002": "Cankerblight: when an enemy (non-MONSTER/VEHICLE) within 6\" fails Battle-shock, you may destroy one model; if used, Daemonic Terror mortals are suppressed for that test.",
        "000009819003": "Maggot Maws: Shooting phase select enemy within 6\"; it takes a Battle-shock test then suffers D3 mortal wounds on 3+; Daemonic Terror mortals are suppressed for that test.",
        "000009987002": "Superior Creation: bearer-only return on a 2+ at end of phase after first destruction (full wounds).",
        "000009987003": "Praesidius: bearer gains Lone Operative and Stealth (no Lone Operative leak while attached).",
        "000009987004": "Fierce Conqueror: start of Fight phase, bearer gains +2 Attacks per 5 enemy models within 6\" until end of phase.",
        "000009987005": "Admonimortis: bearer melee weapons gain +3 Strength, +1 AP, and +1 Damage.",
        "000008367002": "Follow Me Ladz: while leading, bearer unit gains +2\" Move.",
        "000008367003": "Headwoppa's Killchoppa: bearer melee weapons (excluding Extra Attacks) gain Devastating Wounds.",
        "000008367004": "Kunnin' But Brutal: while leading, bearer unit can shoot and charge after Falling Back.",
        "000008367005": "Supa-Cybork Body: bearer gains Feel No Pain 4+.",
        "000010304002": "Knight Diabolus: bearer melee weapons improve WS by 1; while using Diabolic Power, bearer melee weapons gain [LANCE].",
        "000010304003": "Blasphemous Engine: +2 Wounds; Malefic Surge Leadership test can be re-rolled.",
        "000010304004": "Fleshmetal Fusion: +1 Toughness; while using Unnatural Fortitude, bearer gains +1 armor save vs Damage 1.",
        "000010304005": "Bestial Aspect: bearer ranged weapons gain [Assault]; while using Unholy Hunger, may ignore Move/Advance modifiers.",
    }
    if enh_id in explicit:
        return ("Supported", explicit[enh_id])

    status, notes = classify_enhancement_support(description)
    if status == "Supported":
        return (status, notes)
    return (status, notes)


def _stratagem_support(name: str, description: str = "") -> Tuple[str, str, str]:
    name_u = (name or "").strip().upper()
    notes = {
        "COMMAND RE-ROLL": "Queued on roll; executes reroll callback; once-per-phase rule enforced.",
        "COUNTER-OFFENSIVE": "Fight phase: select a unit to fight next after enemy unit fights.",
        "EPIC CHALLENGE": "Fight phase: selected CHARACTER gains Precision for melee attacks.",
        "FIRE OVERWATCH": "Queued on enemy movement; resolves shooting on 6s to hit.",
        "GO TO GROUND": "Shooting phase: INFANTRY gains cover + 6++ until end of phase.",
        "GRENADE": "Shooting phase: 6D6 vs 4+ for mortal wounds within 8\".",
        "HEROIC INTERVENTION": "Charge phase: select unit to charge after enemy charge ends.",
        "INSANE BRAVERY": "Command phase: auto-pass Battle-shock once per battle.",
        "NEW ORDERS": "Command phase: discard a Secondary and draw a new one.",
        "RAPID INGRESS": "Movement phase: place a reserves unit at end of opponent move.",
        "SMOKESCREEN": "Shooting phase: SMOKE unit gains cover + Stealth.",
        "TANK SHOCK": "Charge phase: roll vs Toughness to deal mortals (max 6).",
        "APOPLECTIC FRENZY": "Advance and Charge for a BERZERKERS unit; Berzerker Warband only.",
        "A GRIM WARNING": "Destroyed BLOOD ANGELS unit on a previously controlled objective lets you select a marker to remain under your control until broken.",
        "ARMOUR OF CONTEMPT": "Shooting/Fight phase: targeted ADEPTUS ASTARTES unit worsens AP by 1 vs the attacking unit until it finishes its attacks.",
        "BERZERKER'S WRATH": "Blood Surge distance is fixed at 8\" (no D6 roll) for a BERZERKERS unit.",
        "BERZERKER’S WRATH": "Blood Surge distance is fixed at 8\" (no D6 roll) for a BERZERKERS unit.",
        "BLESSING OF BURNING BLOOD": "Shooting/Fight phase: after enemy targets; BLOOD LEGIONS unit within 6\" of targeted WORLD EATERS grants 5++ (4++ if Boon of Blood active) until end of phase.",
        "BLITZING FIREPOWER": "Shooting phase: ASURYANI unit gains Sustained Hits 1 vs targets within 12\"; if already has Sustained Hits, crits on 5+.",
        "DEATHLESS DUTY": "Fight phase: DEATH COMPANY unit fights on death after the attacker finishes its attacks (until end of phase).",
        "FEIGNED RETREAT": "Movement phase: ASURYANI unit that Fell Back can shoot and charge this turn.",
        "FIRE AND FADE": "Shooting phase: ASURYANI INFANTRY makes Normal move D6+1\" after shooting; cannot charge or embark this turn.",
        "INSENSATE RAMPAGE": "Defensive reaction after targets selected: DEATH COMPANY unit gains Feel No Pain 5+ until end of phase.",
        "LIGHTNING-FAST REACTIONS": "Shooting/Fight phase: targeted ASURYANI (non-Wraith Construct) gets -1 to hit until end of phase.",
        "SKYBORNE SANCTUARY": "End of Fight phase: ASURYANI unit not engaged and wholly within 6\" can embark in friendly Transport.",
        "WEBWAY TUNNEL": "End of opponent Fight phase: ASURYANI INFANTRY wholly within 9\" of battlefield edge goes to Strategic Reserves.",
        "BLOOD OFFERING": "Sticky objective on unit destruction; Berzerker Warband only.",
        "DAEMONIC FURY": "Fight phase: BLOOD LEGIONS unit selects WORLD EATERS unit within 6\" to gain [LANCE] until end of turn; if Daemonic Rage active, also [TWIN-LINKED] this phase.",
        "DAEMONTIDE": "Command phase: WORLD EATERS unit selects BLOOD LEGIONS within 6\" to return destroyed models (1 Mounted / D3 Beast / D6 Infantry).",
        "FRENZIED RESILIENCE": "Fight phase: after enemy targets; WORLD EATERS unit reduces damage by 1.",
        "HACK AND SLASH": "Fight phase: charged WORLD EATERS unit gains +1 AP on melee weapons.",
        "A WORTHY SKULL": "Fight phase: after CHARACTER/MONSTER kill, gain D3 Blood Tithe points and optionally activate Blood Tithe.",
        "SKULLS FOR THE SKULL THRONE!": "Fight phase: after CHARACTER/MONSTER kill, roll Blessings for a unit-only extra blessing.",
        "MURDER-CALL": "End of opponent Fight phase: BLOOD LEGIONS unit not in Engagement Range goes to Strategic Reserves.",
        "SUMMONED BY SLAUGHTER": "Any phase: set up BLOODLETTERS from Reserves wholly within 9\" of destroyed model; >6\" from enemies; once per battle round.",
        "THE FOE FORESEEN": "Shooting/Fight phase: targeted ADEPTUS ASTARTES unit worsens AP by 1 vs the attacking unit until it finishes its attacks.",
        "UNBOUND ARROGANCE": "Coterie of the Conceited pledge increases by 1 (once per battle round).",
        "CRUEL BLADESMAN": "Fight phase: charged unit gains +1 AP on melee weapons (before it has fought).",
        "LIMB FROM LIMB": "Fight phase: charged BLOOD ANGELS unit gains +1 Strength or +1 AP; Red Thirst grants both and applies Battle-shock until end of phase.",
        "RED WRATH": "Movement phase: advanced BLOOD ANGELS unit chooses shoot or charge; Red Thirst grants both and applies Battle-shock until end of turn.",
        "INCESSANT VIOLENCE": "Fight phase: consolidate up to 6\" if the unit can end in Engagement Range.",
        "UNYIELDING FORMS": "Shooting/Fight phase: NECRONS VEHICLE/MOUNTED (non-TITANIC) targeted unit gets -1 to wound if S>T until end of phase.",
        "MERCILESS RECLAMATION": "Shooting/Fight phase: NECRONS (non-TITANIC) unit not yet acted gets +1 to wound vs targets within objective range.",
        "DIMENSIONAL TUNNEL": "Movement phase: NECRONS VEHICLE/MOUNTED (non-TITANIC) can move through models/terrain this phase.",
        "CHRONOSHIFT": "Movement phase: NECRONS VEHICLE/MOUNTED (non-TITANIC) not yet moved treats Advance roll as 6 this phase.",
        "ENDLESS SERVITUDE": "End of Fight phase: NECRONS (non-TITANIC) within controlled objective triggers Reanimation Protocols (D3).",
        "REACTIVE REPOSITION": "Opponent Shooting phase: NECRONS (non-TITANIC) targeted unit makes a Normal move (D6\").",
        "PROFANE SYMBIOSIS": "End of any phase: CHAOS KNIGHTS unit (not Empowered) makes a Malefic Surge; same unit once per battle round.",
        "CORRUPTING TAINT": "Command phase after Malefic Surge: CHAOS KNIGHTS CHARACTER selects controlled objective in range to become sticky until opponent has greater control.",
        "UNLEASH BALEFIRE": "Shooting phase: mark CHAOS KNIGHTS unit; after shooting select a hit enemy, Battle-shock test; on fail, Aflame (-2 Move, -2 Charge) until end of opponent's next turn.",
        "WARP VISION": "Shooting phase: CHAOS KNIGHTS unit ranged weapons ignore cover until end of phase.",
        "DEFIANT TO THE LAST": "Opponent Fight phase: targeted ADEPTUS CUSTODES unit fights on death on 4+ (add 2 if Character) after attacker finishes; then removed.",
        "GILDED CHAMPION": "After a CHARACTER uses a datasheet once-per-battle ability, spend 1CP to grant one extra use (not same phase); once per model.",
        "MANOEUVRE AND FIRE": "Movement phase: ADEPTUS CUSTODES unit can shoot after falling back this turn.",
        "PEERLESS WARRIOR": "Fight phase: selected ADEPTUS CUSTODES unit gains +1 Attacks on melee weapons until end of phase.",
        "SWIFT AS THE EAGLE": "Opponent Shooting phase: targeted ADEPTUS CUSTODES unit makes a Normal move up to 6\" and can move within Engagement Range.",
        "UNLEASH THE LIONS": "Command phase: split Allarus/Aquilon unit on battlefield into 1-model units (leaders split too); Starting Strength 1.",
        "UNBRIDLED CARNAGE": "Fight phase: ORKS unit not yet fought scores critical hits on 5+ in melee until end of phase.",
        "ORKS IS NEVER BEATEN": "Fight phase: targeted ORKS unit fights on death after attacker finishes attacks if it has not fought; then removed.",
        "ERE WE GO": "Movement phase start: ORKS INFANTRY unit gains +2 to Advance and Charge rolls until end of turn.",
        "MOB RULE": "Command phase: select ORKS MOB (10+ models, not below half-strength) and a Battle-shocked ORKS INFANTRY within 6\" to clear Battle-shock.",
        "CAREEN!": "On Deadly Demise roll of 6: ORKS VEHICLE moves (Normal/Fall Back) before explosion; can move over enemy units except MONSTER/VEHICLE.",
        "'ARD AS NAILS": "Opponent Shooting/Fight phase: targeted ORKS unit (excluding Grots/Monsters/Vehicles) suffers -1 to wound until end of phase.",
        "\u2019ARD AS NAILS": "Opponent Shooting/Fight phase: targeted ORKS unit (excluding Grots/Monsters/Vehicles) suffers -1 to wound until end of phase.",
        "CORRUPT REALSPACE": "Command phase: corrupt a controlled objective; sticky until opponent controls it at start/end of any turn; 6\" area counts as Shadow of Chaos.",
        "DAEMONIC INVULNERABILITY": "Opponent Shooting phase: targeted LEGIONES DAEMONICA unit re-rolls invulnerable saves of 1 until end of phase.",
        "DENIZENS OF THE WARP": "Movement phase: Deep Strike arrival can be set up more than 6\" horizontally from enemies this phase.",
        "DRAUGHT OF TERROR": "Shooting/Fight phase: LEGIONES DAEMONICA unit gains +1 AP and re-rolls Wound rolls vs Battle-shocked targets until end of phase.",
        "THE REALM OF CHAOS": "End of opponent turn: up to two Shadow-of-Chaos units (or one other unit) enter Strategic Reserves and return next Movement phase via Deep Strike.",
        "WARP SURGE": "Charge phase: LEGIONES DAEMONICA unit within Shadow of Chaos can charge after advancing this phase.",
    }

    if name_u in IMPLEMENTED_STRATAGEM_NAMES:
        return ("Implemented", notes.get(name_u, "Implemented in engine."), name_u)
    spec = parse_defensive_reaction_stratagem(name, description or "")
    if spec:
        return ("Implemented", defensive_reaction_note(spec), name_u)
    spec = parse_charge_melee_ap_stratagem(name, description or "")
    if spec:
        bonus = int(spec.get("ap_bonus", 1) or 1)
        note = notes.get(name_u, f"Fight phase: charged unit gains +{bonus} AP on melee weapons.")
        return ("Implemented", note, name_u)
    spec = parse_consolidate_move_stratagem(name, description or "")
    if spec:
        max_dist = int(spec.get("max_distance", 0) or 0)
        if spec.get("requires_engagement"):
            note = notes.get(
                name_u,
                f"Fight phase: consolidate up to {max_dist}\" if the unit can end in Engagement Range.",
            )
        else:
            note = notes.get(name_u, f"Fight phase: consolidate up to {max_dist}\".")
        return ("Implemented", note, name_u)
    return ("Not implemented", "No effect logic currently wired.", name_u)


def _extract_restrictions(desc_html: str) -> List[str]:
    if not desc_html:
        return []
    text = desc_html
    if "RESTRICTIONS" not in text.upper():
        return []

    m = re.search(r"RESTRICTIONS</span>(.*?)</ul>", text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        block = m.group(1)
        items = re.findall(r"<li[^>]*>(.*?)</li>", block, flags=re.IGNORECASE | re.DOTALL)
        out = []
        for item in items:
            clean = _strip_html(item)
            if clean:
                out.append(clean)
        return out

    # Fallback: strip tags, take lines after RESTRICTIONS
    clean_text = _strip_html(text)
    upper = clean_text.upper()
    idx = upper.find("RESTRICTIONS")
    if idx == -1:
        return []
    after = clean_text[idx + len("RESTRICTIONS") :]
    parts = [p.strip(" -") for p in after.split("\n") if p.strip()]
    return parts


def _row(cells: Sequence[str], _status: str) -> str:
    tds = "".join(f"<td>{c}</td>" for c in cells)
    return f"<tr>{tds}</tr>"


def _table(headers: Sequence[str], rows: Sequence[Tuple[Sequence[str], str]]) -> str:
    ths = "".join(f"<th>{_escape(h)}</th>" for h in headers)
    body = "".join(_row(cells, status) for cells, status in rows)
    return f"<table><thead><tr>{ths}</tr></thead><tbody>{body}</tbody></table>"

def _load_factions() -> Dict[str, Dict[str, str]]:
    path = os.path.join(WAHA_DIR, "Factions.json")
    if not os.path.exists(path):
        return {}
    raw = _read_json(path)
    out: Dict[str, Dict[str, str]] = {}
    for item in raw:
        fid = item.get("id", "") or ""
        if not fid:
            continue
        out[fid] = {
            "name": item.get("name", "") or fid,
            "link": item.get("link", "") or "",
        }
    return out


def _load_sources() -> Dict[str, dict]:
    path = os.path.join(WAHA_DIR, "Source.json")
    if not os.path.exists(path):
        return {}
    raw = _read_json(path)
    out = {}
    for item in raw:
        sid = str(item.get("id", "") or "").strip()
        if not sid:
            continue
        out[sid] = item
    return out


def _source_is_excluded(source: Optional[dict]) -> bool:
    if not source:
        return False
    name = str(source.get("name", "") or "").lower()
    stype = str(source.get("type", "") or "").lower()
    if "(forge world)" in name or "legends" in name or "warhammer 40,000:" in name:
        return True
    if stype == "boarding actions" or name.strip() == "boarding actions":
        return True
    return False


def _load_detachments() -> Dict[str, dict]:
    path = os.path.join(WAHA_DIR, "Detachments.json")
    raw = _read_json(path)
    out = {}
    for d in raw:
        did = (d.get("id") or "").strip()
        if not did:
            continue
        out[did] = d
    return out


def _detachment_is_boarding(det: dict) -> bool:
    return str(det.get("type", "") or "").strip().lower() == "boarding actions"


def _build_datasheet_map(sources: Optional[Dict[str, dict]] = None) -> Dict[str, dict]:
    raw = _read_json(os.path.join(WAHA_DIR, "Datasheets.json"))
    out = {}
    for ds in raw:
        did = ds.get("id", "") or ""
        if not did:
            continue
        if sources:
            source_id = str(ds.get("source_id", "") or "").strip()
            if source_id and _source_is_excluded(sources.get(source_id)):
                continue
        out[did] = ds
    return out


def _ability_entry_by_name(abilities: List[dict], name: str, faction_id: Optional[str] = None) -> Optional[dict]:
    target = _norm(name)
    best = None
    for a in abilities:
        if _norm(a.get("name", "")) != target:
            continue
        if faction_id and str(a.get("faction_id", "") or "").strip().upper() != faction_id:
            continue
        best = a
        break
    if best is not None:
        return best
    # Fallback without faction match
    for a in abilities:
        if _norm(a.get("name", "")) == target:
            return a
    return None


def _collect_units_for_ability(
    ability_id: str,
    ds_abilities_rows: List[dict],
    ds_map: Dict[str, dict],
    faction_id: Optional[str] = None,
) -> List[str]:
    names = []
    for r in ds_abilities_rows:
        if str(r.get("ability_id", "") or "").strip() != ability_id:
            continue
        dsid = str(r.get("datasheet_id", "") or "").strip()
        ds = ds_map.get(dsid)
        if not ds:
            continue
        fid = str(ds.get("faction_id", "") or "").strip().upper()
        if fid not in SUPPORTED_FACTION_IDS:
            continue
        if faction_id and fid != str(faction_id or "").strip().upper():
            continue
        names.append(ds.get("name", dsid))
    return names


def _collect_units_for_detachment_ability(ability_id: str, ds_det_rows: List[dict], ds_map: Dict[str, dict]) -> List[str]:
    names = []
    for r in ds_det_rows:
        if str(r.get("detachment_ability_id", "") or "").strip() != ability_id:
            continue
        dsid = str(r.get("datasheet_id", "") or "").strip()
        ds = ds_map.get(dsid)
        if not ds:
            continue
        fid = str(ds.get("faction_id", "") or "").strip().upper()
        if fid not in SUPPORTED_FACTION_IDS:
            continue
        names.append(ds.get("name", dsid))
    return names


def _summarize_section_count(items: Iterable[Tuple[str, str]]) -> Tuple[int, int]:
    total = 0
    supported = 0
    for status, _name in items:
        total += 1
        if _status_is_supported(status):
            supported += 1
    return supported, total


def _summary_span(title: str, supported: int, total: int) -> str:
    return _summary_span_with_label(title, supported, total, "abilities")


def _summary_span_with_label(title: str, supported: int, total: int, label: str) -> str:
    label = f"{_escape(title)} ({supported} out of {total} {label} supported)"
    return label


def _details_raw(summary_html: str, body: str) -> str:
    return f"<details><summary>{summary_html}</summary>\n{body}\n</details>"


def _engine_notes(status: str, notes: str) -> str:
    if notes:
        return notes
    key = _norm(status)
    if key in ("supported", "implemented"):
        return "Implemented in engine."
    if key == "partial":
        return "Partially implemented in engine."
    return "No effect logic wired."


def _slugify(name: str) -> str:
    txt = _ascii_text(name)
    txt = re.sub(r"[^a-zA-Z0-9]+", "_", txt).strip("_").lower()
    return txt or "faction"


def _restriction_rule_and_engine(name: str, abilities: List[dict], faction_id: Optional[str]) -> Tuple[str, str]:
    key = _norm(name)
    ability = _ability_entry_by_name(abilities, name, faction_id=faction_id)
    desc = _strip_html(ability.get("description", "")) if ability else ""
    pact_match = re.search(r"cannot select\s+(.+?)\s+as your army faction", desc, flags=re.IGNORECASE)
    if pact_match:
        forbidden = pact_match.group(1).strip().strip(".")
        return (
            f"Army Faction cannot be {forbidden}.",
            "Validated in army detachment restrictions.",
        )
    rules = {
        "freeblades": (
            "Imperial Knights allies only; army must be IMPERIUM; allied Knights cannot be Warlord or take Enhancements; "
            "max 1 TITANIC or 3 ARMIGER, and cannot mix both.",
            "Validated in Army._validate_freeblades.",
        ),
        "disparate paths": (
            "Allows base faction plus HARLEQUINS/YNNARI; other faction keywords are rejected.",
            "Validated in Army.validate_allies.",
        ),
        "corsairs and travelling players": (
            "Allows DRUKHARI plus HARLEQUINS/ANHRATHE; allied units cannot be Warlord or take Enhancements; "
            "points cap enforced by battle size.",
            "Validated in Army._validate_corsairs_and_travelling_players.",
        ),
        "daemonic pact": (
            "LEGIONES DAEMONICA allies allowed only in CSM/Chaos Knights; allies cannot be Warlord or take Enhancements; "
            "points cap enforced and god non-Battleline cannot exceed Battleline.",
            "Validated in Army._validate_daemonic_pact.",
        ),
        "dreadblades": (
            "Chaos Knights allies: only TITANIC or WAR DOG; cannot mix; max 1 TITANIC or 3 WAR DOG.",
            "Validated in Army.validate_dreadblades.",
        ),
        "cult of the dark gods": (
            "Cult ally points cap enforced; cult units forced to Heretic Astartes keywords.",
            "Validated in Army.validate_cult_of_dark_gods.",
        ),
        "space marine chapters": (
            "All Adeptus Astartes units must share a single Chapter keyword; mixed chapters disallowed.",
            "Validated in Army.validate_space_marine_chapters.",
        ),
        "deathwatch": (
            "Deathwatch armies cannot include non-Deathwatch Astartes or banned units; AoI Deathwatch excluded.",
            "Validated in Army.validate_space_marine_chapters.",
        ),
    }
    if key in rules:
        return rules[key]
    return (desc or name, "Validated in army restrictions.")


def _build_faction_content(
    *,
    faction_id: str,
    meta: dict,
    abilities: List[dict],
    det_abilities_by_det: Dict[str, List[dict]],
    enhancements: List[dict],
    stratagems: List[dict],
    detachments: Dict[str, dict],
    ds_abilities_rows: List[dict],
    datasheet_abilities_by_faction: Dict[str, Dict[Tuple[str, ...], dict]],
    datasheet_abilities_by_datasheet: Dict[str, Dict[Tuple[str, ...], dict]],
    datasheets_by_faction: Dict[str, List[dict]],
    options_by_datasheet: Dict[str, List[dict]],
    wargear_by_datasheet: Dict[str, List[dict]],
    keywords_by_datasheet: Dict[str, List[dict]],
    models_by_datasheet: Dict[str, List[dict]],
    models_cost_by_datasheet: Dict[str, List[dict]],
    unit_comp_by_datasheet: Dict[str, List[dict]],
    datasheet_support_overrides: Dict[Tuple[str, str], Tuple[str, str]],
    virtual_unit_names: set[str],
) -> Tuple[str, int, int, int, int, int, int]:
    faction_name = str(meta.get("faction_name", "") or faction_id)
    faction_items: List[Tuple[str, str]] = []
    faction_body: List[str] = []
    det_supported = 0
    det_total = 0
    ds_supported = 0
    ds_total = 0

    # Army rules
    army_rule_rows = []
    for rule_name in list(meta.get("army_rules", []) or []):
        entry = _ability_entry_by_name(abilities, rule_name, faction_id=faction_id)
        desc = entry.get("description", "") if entry else ""
        ability_id = str(entry.get("id", "") or "") if entry else ""
        status, notes = _classify_ability(rule_name, desc, ability_id=ability_id, faction_id=faction_id)
        faction_items.append((status, rule_name))
        army_rule_rows.append(
            (
                [
                    _escape(_status_icon(status)),
                    _escape(rule_name),
                    _desc_block(_strip_html(desc), _engine_notes(status, notes)),
                ],
                status,
            )
        )
    if army_rule_rows:
        faction_body.append("## Army Rules")
        faction_body.append(_table(["Status", "Army Rule", "Description"], army_rule_rows))
        faction_body.append("")

    # Mustering restrictions
    restriction_rows = []
    for restriction in list(meta.get("restrictions", []) or []):
        status, notes = _classify_ability(restriction, "", faction_id=faction_id)
        rules_text, engine_text = _restriction_rule_and_engine(restriction, abilities, faction_id)
        faction_items.append((status, restriction))
        restriction_rows.append(
            (
                [
                    _escape(_status_icon(status)),
                    _escape(restriction),
                    _desc_block(rules_text, engine_text or _engine_notes(status, notes)),
                ],
                status,
            )
        )
    if restriction_rows:
        faction_body.append("## Mustering Restrictions")
        faction_body.append(_table(["Status", "Restriction", "Description"], restriction_rows))
        faction_body.append("")

    # Detachments
    dets = [
        d for d in detachments.values()
        if str(d.get("faction_id", "") or "").strip().upper() == faction_id
        and not _detachment_is_boarding(d)
    ]
    dets.sort(key=lambda d: _norm(d.get("name", "")))
    if dets:
        faction_body.append("## Detachments")
        for det in dets:
            det_total += 1
            det_name = str(det.get("name", "") or "Detachment")
            det_id = str(det.get("id", "") or "").strip()
            det_body: List[str] = []
            det_rule_statuses: List[str] = []
            det_enh_statuses: List[str] = []
            det_strat_statuses: List[str] = []

            # Detachment abilities
            det_ability_rows = []
            det_restrictions: List[str] = []
            for ability in det_abilities_by_det.get(det_id, []):
                name = ability.get("name", "") or ""
                desc = ability.get("description", "") or ""
                ability_id = str(ability.get("id", "") or "")
                status, notes = _classify_ability(name, desc, ability_id=ability_id, faction_id=faction_id)
                faction_items.append((status, name))
                det_rule_statuses.append(status)
                det_ability_rows.append(
                    (
                        [
                            _escape(_status_icon(status)),
                            _escape(name),
                            _desc_block(_strip_html(desc), _engine_notes(status, notes)),
                        ],
                        status,
                    )
                )
                det_restrictions.extend(_extract_restrictions(desc))
            if det_ability_rows:
                det_body.append("**Detachment Abilities**")
                det_body.append(_table(["Status", "Ability", "Description"], det_ability_rows))
                det_body.append("")

            det_restrictions = sorted({r for r in det_restrictions if r}, key=str.lower)
            if not _detachment_has_restrictions(det_id, det_name):
                det_restrictions = []
            if det_restrictions:
                det_restriction_rows = []
                for restriction in det_restrictions:
                    status, notes = _classify_ability(restriction, "", faction_id=faction_id)
                    rules_text, engine_text = _restriction_rule_and_engine(restriction, abilities, faction_id)
                    faction_items.append((status, restriction))
                    det_rule_statuses.append(status)
                    det_restriction_rows.append(
                        (
                            [
                                _escape(_status_icon(status)),
                                _escape(restriction),
                                _desc_block(rules_text, engine_text or _engine_notes(status, notes)),
                            ],
                            status,
                        )
                    )
                det_body.append("**Detachment Restrictions**")
                det_body.append(_table(["Status", "Restriction", "Description"], det_restriction_rows))
                det_body.append("")

            # Enhancements
            det_enh = [e for e in enhancements if str(e.get("detachment_id", "") or "").strip() == det_id]
            if det_enh:
                enh_rows = []
                for enh in det_enh:
                    name = enh.get("name", "") or ""
                    desc = enh.get("description", "") or ""
                    enh_id = str(enh.get("id", "") or "")
                    status, notes = _enhancement_support(name, enh_id, desc)
                    det_enh_statuses.append(status)
                    enh_rows.append(
                        (
                            [
                                _escape(_status_icon(status)),
                                _escape(name),
                                _desc_block(_strip_html(desc), _engine_notes(status, notes)),
                            ],
                            status,
                        )
                    )
                det_body.append("**Enhancements**")
                det_body.append(_table(["Status", "Enhancement", "Description"], enh_rows))
                det_body.append("")

            # Stratagems
            det_strats = []
            for s in stratagems:
                if str(s.get("detachment_id", "") or "").strip() != det_id:
                    continue
                ttype = (s.get("type", "") or "").strip().lower()
                if "boarding" in ttype or "challenger" in ttype:
                    continue
                det_strats.append(s)
            if det_strats:
                det_strats.sort(key=lambda s: _norm(s.get("name", "")))
                strat_rows = []
                for s in det_strats:
                    status, notes, _ = _stratagem_support(s.get("name", ""), s.get("description", ""))
                    det_strat_statuses.append(status)
                    strat_rows.append(
                        (
                            [
                                _escape(_status_icon(status)),
                                _escape(s.get("name", "")),
                                f"<code>{_escape(s.get('id', ''))}</code>",
                                _escape(s.get("type", "")),
                                _escape(s.get("cp_cost", "")),
                                _escape(s.get("turn", "")),
                                _escape(s.get("phase", "")),
                                _escape(notes),
                            ],
                            status,
                        )
                    )
                det_body.append("**Stratagems**")
                det_body.append(
                    _table(
                        ["Status", "Stratagem", "ID", "Type", "CP", "Turn", "Phase", "Notes"],
                        strat_rows,
                    )
                )
                det_body.append("")

            if not det_body:
                det_body.append("_No detachment data available._")
            faction_body.append(_details_raw(_escape(det_name), "\n".join(det_body)))
            faction_body.append("")
            det_rules_supported = bool(det_rule_statuses) and all(
                _status_is_supported(status) for status in det_rule_statuses
            )
            det_enh_supported = (not det_enh_statuses) or all(
                _status_is_supported(status) for status in det_enh_statuses
            )
            det_strat_supported = (not det_strat_statuses) or all(
                _status_is_supported(status) for status in det_strat_statuses
            )
            if det_rules_supported and det_enh_supported and det_strat_supported:
                det_supported += 1

    # Datasheet abilities
    ds_ability_rows = []
    ability_entries = list(datasheet_abilities_by_faction.get(faction_id, {}).values())
    if ability_entries:
        filtered_entries = []
        for entry in ability_entries:
            units = set(entry.get("units") or set())
            if units:
                kept = {u for u in units if u not in virtual_unit_names}
                kept = {u for u in kept if not _is_kill_team_unit(u)}
                if not kept:
                    continue
                entry = dict(entry)
                entry["units"] = kept
            filtered_entries.append(entry)
        ability_entries = filtered_entries
    ability_entries.sort(key=lambda e: (_norm(e.get("name", "")), _norm(_strip_html(e.get("description", "")))))
    name_variants: Dict[str, set[str]] = {}
    for entry in ability_entries:
        nm = _norm(entry.get("name", "") or "")
        if not nm:
            continue
        desc_norm = _norm(_strip_html(entry.get("description", "")))
        name_variants.setdefault(nm, set()).add(desc_norm)
    ambiguous_names = {nm for nm, descs in name_variants.items() if len(descs) > 1}
    for entry in ability_entries:
        name = entry.get("name", "") or ""
        desc = entry.get("description", "") or ""
        ability_id = str(entry.get("ability_id", "") or "")
        name_norm = _norm(name)
        ds_ids = sorted({str(d or "").strip() for d in (entry.get("datasheet_ids") or set()) if str(d or "").strip()})
        if name_norm and name_norm in ambiguous_names:
            if len(ds_ids) == 1:
                status, notes = _classify_ability(
                    name,
                    desc,
                    ability_id=ability_id,
                    faction_id=faction_id,
                    datasheet_id=ds_ids[0],
                )
            elif ds_ids:
                statuses = []
                notes_list = []
                for dsid in ds_ids:
                    st, nt = _classify_ability(
                        name,
                        desc,
                        ability_id=ability_id,
                        faction_id=faction_id,
                        datasheet_id=dsid,
                    )
                    statuses.append(st)
                    notes_list.append(nt)
                if len(set(statuses)) == 1:
                    status = statuses[0]
                    notes = next((n for n in notes_list if n), "")
                else:
                    status, notes = _abilities_support_summary(statuses)
            else:
                status, notes = _classify_ability(name, desc, ability_id=ability_id, faction_id=faction_id)
        else:
            status, notes = _classify_ability(name, desc, ability_id=ability_id, faction_id=faction_id)
        faction_items.append((status, name))
        units = sorted({u for u in (entry.get("units") or set()) if u}, key=lambda s: s.lower())
        ds_ability_rows.append(
            (
                [
                    _escape(_status_icon(status)),
                    _escape(name),
                    _format_units(units),
                    _desc_block(_strip_html(desc), _engine_notes(status, notes)),
                ],
                status,
            )
        )
    if ds_ability_rows:
        faction_body.append("## Datasheet Abilities")
        faction_body.append(_table(["Status", "Ability", "Units", "Description"], ds_ability_rows))
        faction_body.append("")

    # Datasheet support summary
    ds_units = list(datasheets_by_faction.get(faction_id, []) or [])
    ds_units = [ds for ds in ds_units if not _is_kill_team_unit(ds.get("name", ""))]
    if ds_units:
        ds_units.sort(key=lambda d: (_norm(d.get("name", "")), str(d.get("id", "") or "")))
        ds_total = len(ds_units)
        ds_rows = []
        for ds in ds_units:
            dsid = str(ds.get("id", "") or "").strip()
            name = str(ds.get("name", "") or dsid)
            ability_entries = list(datasheet_abilities_by_datasheet.get(dsid, {}).values())
            ability_statuses: List[str] = []
            for entry in ability_entries:
                ab_name = entry.get("name", "") or ""
                ab_desc = entry.get("description", "") or ""
                ab_id = str(entry.get("ability_id", "") or "")
                if _norm(ab_name) in ambiguous_names:
                    ab_status, _ab_notes = _classify_ability(
                        ab_name,
                        ab_desc,
                        ability_id=ab_id,
                        faction_id=faction_id,
                        datasheet_id=dsid,
                    )
                else:
                    ab_status, _ab_notes = _classify_ability(
                        ab_name,
                        ab_desc,
                        ability_id=ab_id,
                        faction_id=faction_id,
                    )
                ability_statuses.append(ab_status)

            ability_status, ability_note = _abilities_support_summary(ability_statuses)
            options_status, options_note = _optional_wargear_support(options_by_datasheet.get(dsid, []))
            wargear_kw_status, wargear_kw_note = _wargear_keywords_support(wargear_by_datasheet.get(dsid, []))
            points_status, points_note = _points_support(models_cost_by_datasheet.get(dsid, []))
            keywords_status, keywords_note = _keywords_support(keywords_by_datasheet.get(dsid, []))
            if _is_spawn_only_datasheet(ability_entries, models_cost_by_datasheet.get(dsid, [])):
                points_status, points_note = ("Supported", "")

            damaged_w = str(ds.get("damaged_w", "") or "").strip()
            damaged_desc = str(ds.get("damaged_description", "") or "").strip()
            if damaged_w and damaged_desc:
                key = _damaged_profile_pattern_key(damaged_desc)
                damaged_status, damaged_note = _damaged_profile_support_for_key(key)
            else:
                damaged_status, damaged_note = ("Supported", "No damaged profile.")

            other_status, other_note = _other_sections_support(
                unit_comp_entries=unit_comp_by_datasheet.get(dsid, []),
                model_entries=models_by_datasheet.get(dsid, []),
                transport_text=str(ds.get("transport", "") or ""),
            )

            categories = [
                ("Abilities", ability_status, ability_note),
                ("Wargear options", options_status, options_note),
                ("Wargear keywords", wargear_kw_status, wargear_kw_note),
                ("Points", points_status, points_note),
                ("Keywords", keywords_status, keywords_note),
                ("Damaged profile", damaged_status, damaged_note),
                ("Other sections", other_status, other_note),
            ]

            status, note = _datasheet_support_status(
                faction_id=faction_id,
                datasheet_name=name,
                categories=categories,
                overrides=datasheet_support_overrides,
            )
            if _status_is_supported(status):
                ds_supported += 1
            ds_rows.append(
                (
                    [
                        _escape(_status_icon(status)),
                        _escape(name),
                        _escape(note),
                    ],
                    status,
                )
            )
        faction_body.append("## Datasheets")
        faction_body.append(_table(["Status", "Unit", "Notes"], ds_rows))
        faction_body.append("")

    supported, total = _summarize_section_count(faction_items)
    header = [
        f"# {faction_name} Ability Support",
        "",
        "Generated from `wahapedia_data/*.json` using `scripts/generate_ability_support_matrix.py`.",
        "",
        f"Back to [Ability Support Matrix](../ABILITY_SUPPORT_MATRIX.md).",
        "",
        "## Legend",
        _table(
            ["Status", "Meaning"],
            [
                ([_escape(_status_icon("supported")), "Implemented in engine."], "Supported"),
                ([_escape(_status_icon("partial")), "Partially implemented in engine."], "Partial"),
                ([_escape(_status_icon("not implemented")), "Not implemented."], "Not implemented"),
            ],
        ),
        "",
    ]
    return (
        "\n".join(header + faction_body).rstrip() + "\n",
        supported,
        total,
        det_supported,
        det_total,
        ds_supported,
        ds_total,
    )


def _build_matrix() -> str:
    abilities = _read_json(os.path.join(WAHA_DIR, "Abilities.json"))
    det_abilities_rows = _read_json(os.path.join(WAHA_DIR, "Detachment_abilities.json"))
    ds_abilities_rows = _read_json(os.path.join(WAHA_DIR, "Datasheets_abilities.json"))
    ds_det_rows = _read_json(os.path.join(WAHA_DIR, "Datasheets_detachment_abilities.json"))
    ds_options_rows = _read_json(os.path.join(WAHA_DIR, "Datasheets_options.json"))
    ds_wargear_rows = _read_json(os.path.join(WAHA_DIR, "Datasheets_wargear.json"))
    ds_keywords_rows = _read_json(os.path.join(WAHA_DIR, "Datasheets_keywords.json"))
    ds_models_rows = _read_json(os.path.join(WAHA_DIR, "Datasheets_models.json"))
    ds_models_cost_rows = _read_json(os.path.join(WAHA_DIR, "Datasheets_models_cost.json"))
    ds_unit_comp_rows = _read_json(os.path.join(WAHA_DIR, "Datasheets_unit_composition.json"))
    enhancements = _read_json(os.path.join(WAHA_DIR, "Enhancements.json"))
    stratagems = _read_json(os.path.join(WAHA_DIR, "Stratagems.json"))
    detachments = _load_detachments()
    sources = _load_sources()
    ds_map = _build_datasheet_map(sources)
    virtual_datasheet_ids = {dsid for dsid, ds in ds_map.items() if _is_virtual_datasheet(ds)}
    virtual_unit_names = {ds.get("name", "") or "" for dsid, ds in ds_map.items() if dsid in virtual_datasheet_ids}

    global DETACHMENT_ABILITY_IDS
    DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in det_abilities_rows
        if str(row.get("id", "") or "").strip()
    }

    _seed_ability_support_maps(abilities, det_abilities_rows)

    abilities_by_id = {str(a.get("id", "") or ""): a for a in abilities if a.get("id")}

    det_abilities_by_det: Dict[str, List[dict]] = {}
    for row in det_abilities_rows:
        det_id = str(row.get("detachment_id", "") or "").strip()
        if not det_id:
            continue
        det_abilities_by_det.setdefault(det_id, []).append(row)

    enh_by_det: Dict[str, List[dict]] = {}
    for row in enhancements:
        det_id = str(row.get("detachment_id", "") or "").strip()
        if not det_id:
            continue
        enh_by_det.setdefault(det_id, []).append(row)

    strats_by_det: Dict[str, List[dict]] = {}
    for row in stratagems:
        det_id = str(row.get("detachment_id", "") or "").strip()
        if not det_id:
            continue
        ttype = (row.get("type", "") or "").strip().lower()
        if "boarding" in ttype or "challenger" in ttype:
            continue
        strats_by_det.setdefault(det_id, []).append(row)

    options_by_datasheet: Dict[str, List[dict]] = {}
    for row in ds_options_rows:
        dsid = str(row.get("datasheet_id", "") or "").strip()
        if not dsid:
            continue
        options_by_datasheet.setdefault(dsid, []).append(row)

    wargear_by_datasheet: Dict[str, List[dict]] = {}
    for row in ds_wargear_rows:
        dsid = str(row.get("datasheet_id", "") or "").strip()
        if not dsid:
            continue
        wargear_by_datasheet.setdefault(dsid, []).append(row)

    keywords_by_datasheet: Dict[str, List[dict]] = {}
    for row in ds_keywords_rows:
        dsid = str(row.get("datasheet_id", "") or "").strip()
        if not dsid:
            continue
        keywords_by_datasheet.setdefault(dsid, []).append(row)

    models_by_datasheet: Dict[str, List[dict]] = {}
    for row in ds_models_rows:
        dsid = str(row.get("datasheet_id", "") or "").strip()
        if not dsid:
            continue
        models_by_datasheet.setdefault(dsid, []).append(row)

    models_cost_by_datasheet: Dict[str, List[dict]] = {}
    for row in ds_models_cost_rows:
        dsid = str(row.get("datasheet_id", "") or "").strip()
        if not dsid:
            continue
        models_cost_by_datasheet.setdefault(dsid, []).append(row)

    unit_comp_by_datasheet: Dict[str, List[dict]] = {}
    for row in ds_unit_comp_rows:
        dsid = str(row.get("datasheet_id", "") or "").strip()
        if not dsid:
            continue
        unit_comp_by_datasheet.setdefault(dsid, []).append(row)

    abilities_rows_by_datasheet: Dict[str, List[dict]] = {}
    datasheet_abilities_by_faction: Dict[str, Dict[Tuple[str, ...], dict]] = {}
    datasheet_abilities_by_datasheet: Dict[str, Dict[Tuple[str, ...], dict]] = {}
    for row in ds_abilities_rows:
        dsid = str(row.get("datasheet_id", "") or "").strip()
        if dsid in virtual_datasheet_ids:
            continue
        ds = ds_map.get(dsid)
        if not ds:
            continue
        fid = str(ds.get("faction_id", "") or "").strip().upper()
        if fid not in SUPPORTED_FACTION_IDS:
            continue

        ability_id = str(row.get("ability_id", "") or "").strip()
        entry = abilities_by_id.get(ability_id) if ability_id else None
        name = (entry.get("name", "") if entry else "") or row.get("name", "") or ""
        desc = (entry.get("description", "") if entry else "") or row.get("description", "") or ""
        if not name and not desc:
            continue
        if not name:
            name = "Unnamed ability"

        if ability_id:
            key = ("id", ability_id)
        else:
            key = ("row", _norm(name), _norm(_strip_html(desc)))

        bucket = datasheet_abilities_by_faction.setdefault(fid, {})
        if key not in bucket:
            bucket[key] = {
                "name": name,
                "description": desc,
                "ability_id": ability_id,
                "units": set(),
                "datasheet_ids": set(),
            }
        bucket[key]["units"].add(ds.get("name", dsid))
        bucket[key]["datasheet_ids"].add(dsid)

        ds_bucket = datasheet_abilities_by_datasheet.setdefault(dsid, {})
        if key not in ds_bucket:
            ds_bucket[key] = {"name": name, "description": desc, "ability_id": ability_id}
        abilities_rows_by_datasheet.setdefault(dsid, []).append(row)

    datasheets_by_faction: Dict[str, List[dict]] = {}
    for ds in ds_map.values():
        if _is_virtual_datasheet(ds):
            continue
        fid = str(ds.get("faction_id", "") or "").strip().upper()
        if fid not in SUPPORTED_FACTION_IDS:
            continue
        datasheets_by_faction.setdefault(fid, []).append(ds)

    row_blacklist = {"datasheet_id", "line", "line_in_wargear"}

    def _datasheet_signature(ds: dict) -> tuple:
        dsid = str(ds.get("id", "") or "").strip()
        return (
            _norm(ds.get("role", "")),
            _norm(ds.get("transport", "")),
            _norm(ds.get("damaged_w", "")),
            _norm(_strip_html(ds.get("damaged_description", ""))),
            _freeze_rows(unit_comp_by_datasheet.get(dsid, []), blacklist=row_blacklist),
            _freeze_rows(models_by_datasheet.get(dsid, []), blacklist=row_blacklist),
            _freeze_rows(models_cost_by_datasheet.get(dsid, []), blacklist=row_blacklist),
            _freeze_rows(options_by_datasheet.get(dsid, []), blacklist=row_blacklist),
            _freeze_rows(wargear_by_datasheet.get(dsid, []), blacklist=row_blacklist),
            _freeze_rows(keywords_by_datasheet.get(dsid, []), blacklist=row_blacklist),
            _freeze_rows(abilities_rows_by_datasheet.get(dsid, []), blacklist=row_blacklist),
        )

    def _dedupe_datasheets_by_name(ds_list: List[dict]) -> Tuple[List[dict], List[dict]]:
        by_name: Dict[str, List[dict]] = {}
        for ds in ds_list:
            by_name.setdefault(_norm(ds.get("name", "")), []).append(ds)
        deduped: List[dict] = []
        conflicts: List[dict] = []
        for name_norm, group in by_name.items():
            if len(group) == 1:
                deduped.append(group[0])
                continue
            sig_map: Dict[tuple, List[dict]] = {}
            for ds in group:
                sig_map.setdefault(_datasheet_signature(ds), []).append(ds)
            if len(sig_map) == 1:
                keep = sorted(group, key=lambda d: str(d.get("id", "") or ""))[0]
                deduped.append(keep)
                continue
            conflicts.append({
                "name": group[0].get("name", "") or name_norm,
                "entries": [
                    {
                        "id": str(ds.get("id", "") or "").strip(),
                        "source": str(sources.get(ds.get("source_id", ""), {}).get("name", "") or "").strip(),
                    }
                    for ds in group
                ],
            })
            deduped.extend(group)
        return deduped, conflicts

    dedupe_conflicts: List[dict] = []
    deduped_by_faction: Dict[str, List[dict]] = {}
    for fid, ds_list in datasheets_by_faction.items():
        deduped, conflicts = _dedupe_datasheets_by_name(ds_list)
        deduped_by_faction[fid] = deduped
        dedupe_conflicts.extend(conflicts)
    datasheets_by_faction = deduped_by_faction

    if dedupe_conflicts:
        print("⚠️ Datasheets with same name but different content detected:")
        for entry in dedupe_conflicts:
            parts = []
            for item in entry.get("entries", []):
                sid = item.get("id", "")
                src = item.get("source", "")
                parts.append(f"{sid} ({src})" if src else sid)
            print(f" - {entry.get('name', '')}: {', '.join(parts)}")

    datasheet_support_overrides = _datasheet_support_by_name_faction()

    lines: List[str] = []
    lines.append("# Ability support matrix (Wahapedia)")
    lines.append("")
    lines.append("Generated from `wahapedia_data/*.json` using `scripts/generate_ability_support_matrix.py`.")
    lines.append("Enhancements and detachment abilities are only marked Supported when all rule clauses are consumed by implemented patterns.")
    lines.append("")
    lines.append("## Legend")
    legend_rows = [
        ([_escape(_status_icon("supported")), "Implemented in engine."], "Supported"),
        ([_escape(_status_icon("partial")), "Partially implemented in engine."], "Partial"),
        ([_escape(_status_icon("not implemented")), "Not implemented."], "Not implemented"),
    ]
    lines.append(_table(["Status", "Meaning"], legend_rows))
    lines.append("")

    # ---------------- Core section ----------------
    core_abilities = [a for a in abilities if not a.get("faction_id")]
    core_abilities.sort(key=lambda a: _norm(a.get("name", "")))
    core_rows = []
    core_items: List[Tuple[str, str]] = []
    for ab in core_abilities:
        name = ab.get("name", "") or ""
        desc = ab.get("description", "") or ""
        ability_id = str(ab.get("id", "") or "")
        status, notes = _classify_ability(name, desc, ability_id=ability_id, faction_id="")
        core_items.append((status, name))
        core_rows.append(
            (
                [
                    _escape(_status_icon(status)),
                    _escape(name),
                    _engine_block(_engine_notes(status, notes)),
                ],
                status,
            )
        )
    core_table = _table(["Status", "Ability", "Description"], core_rows)

    core_strats = []
    for s in stratagems:
        if (s.get("faction_id") or "").strip():
            continue
        ttype = (s.get("type", "") or "").strip().lower()
        if "core" not in ttype:
            continue
        if "boarding" in ttype or "challenger" in ttype:
            continue
        core_strats.append(s)

    def _id_key(entry: dict) -> int:
        try:
            return int((entry.get("id") or "0").strip())
        except Exception:
            return 0

    by_name: Dict[str, dict] = {}
    for entry in core_strats:
        name_key = _norm(entry.get("name", ""))
        if not name_key:
            continue
        prev = by_name.get(name_key)
        if prev is None or _id_key(entry) > _id_key(prev):
            by_name[name_key] = entry
    core_strats = list(by_name.values())
    core_strats.sort(key=lambda e: _norm(e.get("name", "")))

    core_strat_rows = []
    core_strat_items: List[Tuple[str, str]] = []
    for s in core_strats:
        status, notes, _ = _stratagem_support(s.get("name", ""), s.get("description", ""))
        core_strat_items.append((status, s.get("name", "") or ""))
        core_strat_rows.append(
            (
                [
                    _escape(_status_icon(status)),
                    _escape(s.get("name", "")),
                    f"<code>{_escape(s.get('id', ''))}</code>",
                    _escape(s.get("type", "")),
                    _escape(s.get("cp_cost", "")),
                    _escape(s.get("turn", "")),
                    _escape(s.get("phase", "")),
                    _escape(notes),
                ],
                status,
            )
        )
    core_strat_table = _table(
        ["Status", "Stratagem", "ID", "Type", "CP", "Turn", "Phase", "Notes"],
        core_strat_rows,
    )

    core_supported, core_total = _summarize_section_count(core_items)
    core_body = "\n".join(
        [
            "### Core Abilities",
            core_table,
        ]
    )
    lines.append(_details_raw(_summary_span("Core", core_supported, core_total), core_body))
    lines.append("")

    core_strat_supported, core_strat_total = _summarize_section_count(core_strat_items)
    core_strat_body = "\n".join(
        [
            "### Core Stratagems",
            core_strat_table,
        ]
    )
    lines.append(
        _details_raw(
            _summary_span_with_label("Core Stratagems", core_strat_supported, core_strat_total, "stratagems"),
            core_strat_body,
        )
    )
    lines.append("")

    # ---------------- Faction summary + files ----------------
    os.makedirs(FACTION_DOCS_DIR, exist_ok=True)
    summary_rows = []
    summary_entries = []
    for faction_id, meta in FACTION_RULE_METADATA.items():
        if faction_id not in SUPPORTED_FACTION_IDS:
            continue
        faction_name = str(meta.get("faction_name", "") or faction_id)
        content, supported, total, det_supported, det_total, ds_supported, ds_total = _build_faction_content(
            faction_id=faction_id,
            meta=meta,
            abilities=abilities,
            det_abilities_by_det=det_abilities_by_det,
            enhancements=enhancements,
            stratagems=stratagems,
            detachments=detachments,
            ds_abilities_rows=ds_abilities_rows,
            datasheet_abilities_by_faction=datasheet_abilities_by_faction,
            datasheet_abilities_by_datasheet=datasheet_abilities_by_datasheet,
            datasheets_by_faction=datasheets_by_faction,
            options_by_datasheet=options_by_datasheet,
            wargear_by_datasheet=wargear_by_datasheet,
            keywords_by_datasheet=keywords_by_datasheet,
            models_by_datasheet=models_by_datasheet,
            models_cost_by_datasheet=models_cost_by_datasheet,
            unit_comp_by_datasheet=unit_comp_by_datasheet,
            datasheet_support_overrides=datasheet_support_overrides,
            virtual_unit_names=virtual_unit_names,
        )
        slug = _slugify(faction_name)
        rel_path = f"factions/{slug}.md"
        out_path = os.path.join(FACTION_DOCS_DIR, f"{slug}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        summary_entries.append(
            (faction_name, supported, total, det_supported, det_total, ds_supported, ds_total, rel_path)
        )

    summary_entries.sort(key=lambda t: t[0].lower())
    for faction_name, supported, total, det_supported, det_total, ds_supported, ds_total, rel_path in summary_entries:
        status = _summary_status_with_coverage(
            supported,
            total,
            det_supported,
            det_total,
            ds_supported,
            ds_total,
        )
        summary_rows.append(
            (
                [
                    _escape(faction_name),
                    _escape(
                        _summary_icon_with_coverage(
                            supported,
                            total,
                            det_supported,
                            det_total,
                            ds_supported,
                            ds_total,
                        )
                    ),
                    _escape(f"{det_supported} out of {det_total}"),
                    _escape(f"{ds_supported} out of {ds_total}"),
                    f"<a href=\"{_escape(rel_path)}\">View</a>",
                ],
                status,
            )
        )
    lines.append("## Factions")
    lines.append(
        _table(
            [
                "Faction",
                "Status",
                "Supported Detachments",
                "Supported Datasheets",
                "Link",
            ],
            summary_rows,
        )
    )

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    os.makedirs(DOCS_DIR, exist_ok=True)
    content = _build_matrix()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {OUT_PATH}")
    _cleanup_audit_artifacts()
    return 0


def _cleanup_audit_artifacts() -> None:
    paths = [
        os.path.join(DOCS_DIR, "ability_audit_worklist.tsv"),
        os.path.join(DOCS_DIR, "ability_audit_worklist_we.tsv"),
        os.path.join(DOCS_DIR, "ability_audit_we_details.txt"),
    ]
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            continue


if __name__ == "__main__":
    raise SystemExit(main())
