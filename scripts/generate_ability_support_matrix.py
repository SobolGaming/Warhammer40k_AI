
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
import logging
logger = logging.getLogger(__name__)


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


def _canon_stratagem_name(value: str) -> str:
    text = str(value or "")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = re.sub(r"\s+", " ", text).strip()
    return text.upper()


IMPLEMENTED_STRATAGEM_NAMES_CANONICAL = {
    _canon_stratagem_name(item) for item in IMPLEMENTED_STRATAGEM_NAMES
}


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
        "Manifold Maladies": (
            r"at the start of the battle round you can select one of the plagues listed in nurgle(?:s| s) gift",
            r"until the end of the battle that is your chosen plague instead of any previously chosen plague",
        ),
        "Miasmic Bombardment": (
            r"at the start of the battle round select a number of enemy units more than 12(?: away)? from every model from your army that is on the battlefield",
            r"until the end of the battle round those enemy units are afflicted",
            r"the maximum number of units you can select in this way depends on the battle size as shown below",
        ),
        "Numberless Horde": (
            r"in your command phase in each of the following battle rounds depending on your chosen battle size add a new poxwalkers unit with a starting strength of 10 to your army in strategic reserves",
            r"battle size battle rounds incursion 2 ?3 strike force 2 ?3 ?4 onslaught 2 ?3 ?4 ?5",
            r"poxwalkers units from your army gain the battleline keyword",
        ),
        "Reverberant Rancidity": (
            r"while a plague legions unit from your army is within 7 of one or more death guard units from your army that plague legions unit has the nurgles gift ability",
            r"while a death guard unit from your army is within 7 of one or more plague legions units from your army add 3 to that death guard units contagion range",
            r"you can include plague legions units in your army even though they do not have the death guard faction keyword",
            r"the combined points cost of such units you can include in your army is",
            r"incursion up to 500 pts",
            r"strike force up to 1000 pts",
            r"onslaught up to 1500 pts",
            r"no plague legions models from your army can be your warlord",
        ),
        "Ride the Wind": (
            r"in addition at the end of your opponents turn you can select a number of asuryani mounted or vyper units from your army excluding units within engagement range of one or more enemy units then remove those units from the battlefield and place them into strategic reserves",
            r"the maximum number of units you can select depends on the battle size as shown below",
            r"windriders units from your army gain the battleline keyword",
        ),
        "Artillery Support": (
            r"at the start of the battle round select one of the following types of artillery support",
            r"roll one d6 for each enemy unit that is more than 12 from every model from your army that is on the battlefield",
            r"on a 5 until the end of the battle round that unit is shaken",
            r"while a unit is shaken subtract 2 from its move characteristic and subtract 2 from charge rolls made for it",
            r"select a number of enemy units more than 12 from every model from your army that is on the battlefield",
            r"until the end of the battle round those enemy units are scattered",
            r"while a unit is scattered it cannot have the benefit of cover",
            r"select a number of units from your army",
            r"until the end of the battle round those units have the stealth ability",
            r"the maximum number of units that can be shaken by this rule in each battle round depends on the battle size as shown below",
            r"the maximum number of units you can select in this way depends on the battle size as shown below",
        ),
        "Shepherds of the Dead": (
            r"each time an asuryani psyker model from your army is destroyed by an enemy unit that enemy unit gains a vengeful dead token",
            r"each time a wraith construct model from your army makes an attack that targets a unit with one or more vengeful dead tokens add 1 to the hit roll and add 1 to the wound roll",
            r"asuryani psyker models from your army have the following ability",
            r"while a wraithblades wraithguard or wraithlord unit from your army is within 12 of this model that unit has the battle focus ability",
            r"wraithblades and wraithguard units from your army gain the battleline keyword",
        ),
        "Skilled Crews": (
            r"ranged weapons equipped by aeldari vehicle models from your army have the assault ability and you can reroll advance rolls made for aeldari vehicle fly units from your army",
            r"ranged weapons equipped by aeldari vehicle models from your army have the assault ability",
            r"you can reroll advance rolls made for aeldari vehicle fly units from your army",
        ),
        "Fervent Purgation": (
            r"ranged weapons equipped by adepta sororitas models from your army have the assault ability and each time an attack made with such a weapon targets a unit within 6 add 1 to the strength characteristic of that attack",
        ),
        "Sacred Rites": (
            r"each adepta sororitas unit from your army can perform up to two acts of faith per phase instead of just one",
        ),
        "Righteous Purpose": (
            r"in your command phase you can select up to 3 adepta sororitas units from your army including units that are embarked within transports until the start of your next command phase those units are righteous",
            r"while a unit is righteous",
            r"add 1 to the move characteristic of models in that unit",
            r"improve the leadership characteristic of models in that unit by 1",
            r"improve the weapon skill and ballistic skill characteristics of weapons equipped by battle sisters squad celestian sacresants and paragon warsuits models in that unit by 1",
            r"while a celestian sacresants unit from your army is not battle shocked add 1 to the objective control characteristic of celestian sacresants models in that unit",
        ),
        "Desperate for Redemption": (
            r"at the start of the battle round you can select one of the following vows of atonement to be active for your army until the start of the next battle round",
            r"you can only select each vow of atonement once per battle",
            r"add 3 to the move characteristic of penitent models from your army",
            r"each time a unit from your army is selected to fight if that unit made a charge move this turn until the end of the phase add 1 to the attacks and strength characteristics of melee weapons equipped by penitent models in that unit",
            r"each time a penitent model from your army is destroyed by a melee attack if that model has not fought this phase roll one d6",
            r"on a 2 do not remove it from play",
            r"the destroyed model can fight after the attacking unit has finished making its attacks and is then removed from play",
        ),
        "Desperate Devotion": (
            r"each time a damned unit from your army with the dark pacts ability is selected to make a normal or advance move or declare a charge excluding units that arrived from reserves this turn it can make a desperate pact(?: see below)?",
            r"if it does until the end of the phase add 2 to the move characteristic of models in that unit and add 2 to charge rolls made for that unit",
            r"each time a unit makes a desperate pact it must first take a leadership test",
            r"if that test is failed that unit suffers d3 mortal wounds before any effects of that desperate pact are resolved",
        ),
        "Experimental Augmentations": (
            r"at the start of the battle select which augmentations are active for heretic astartes infantry models excluding damned models from your army until the end of the battle",
            r"to do so either select one from the list below or randomly determine two by rolling two d6",
            r"if fabius bile is your warlord when randomly determining your augmentations you can reroll one or both of the dice",
            r"duplicated augmentations have no additional effect",
            r"add 1 to the attacks characteristic of melee weapons equipped by this model",
            r"add 2 to the move characteristic of this model",
            r"improve the weapon skill characteristic of melee weapons equipped by this model by 1",
            r"improve the toughness characteristic of this model by 1",
            r"add 1 to the strength characteristic of melee weapons equipped by this model",
            r"improve the ballistic skill characteristic of ranged weapons equipped by this model by 1",
        ),
        "Masters of Misdirection": (
            r"in the declare battle formations step you can select a number of legionaries and cultist mob units from your army",
            r"until the end of the battle those units and any character units attached to them excluding epic heroes have the infiltrators ability",
            r"the maximum number of units you can select in this way depends on the battle size as shown below",
            r"incursion up to 2 units up to 2 units",
            r"strike force up to 3 units up to 3 units",
            r"onslaught up to 4 units up to 4 units",
        ),
        "Terror Descends (Aura)": (
            r"in the battle shock step of your opponent(?:s| s) command phase if an enemy unit that is below its starting strength is within 12 of one or more heretic astartes units from your army that enemy unit must take a battle shock test",
            r"each time an enemy unit within 12 of one or more heretic astartes units from your army takes a battle shock test subtract 1 from the result",
            r"enemy units affected by this detachment rule do not need to take any other battle shock tests in the same phase",
        ),
        "Terror Made Manifest": (
            r"in the battle shock step of your opponent(?:s| s) command phase if an enemy unit that is below its starting strength is within 12 of one or more heretic astartes units from your army that enemy unit must take a battle shock test subtracting 1 from the result",
            r"enemy units affected by this detachment rule do not need to take any other battle shock tests in the same phase",
            r"each time a heretic astartes model from your army makes an attack that targets a unit that is below half strength add 1 to the hit roll",
            r"each time an attack targets a heretic astartes unit from your army if the attacking model is battle shocked subtract 1 from the hit roll",
            r"each time a heretic astartes model from your army makes an attack that targets a battle shocked unit add 1 to the wound roll",
        ),
        "Marks of Chaos": (
            r"when mustering your army when you select a heretic astartes unit to include in your army if that unit is not an epic hero and does not already have one of the following keywords you must select one for that unit and note it on your army roster",
            r"each time a unit with one of these keywords gains a weapon ability as the result of a dark pact and does not fail the resulting leadership test until the end of the phase that unit gains the associated ability below",
            r"units that gained lethal hits",
            r"each time a model in this unit makes a melee attack an unmodified hit roll of 5 scores a critical hit",
            r"each time a model in this unit makes a ranged attack an unmodified hit roll of 5 scores a critical hit",
            r"each time a model in this unit makes an attack reroll a hit roll of 1",
            r"units that gained sustained hits 1",
            r"you cannot select the khorne keyword for a psyker unit",
            r"a character unit can only be attached to a unit if both units share the same keyword from the list above",
            r"a unit can only embark within or start the battle embarked within a transport if both of those units share the same keyword from the list above",
        ),
        "Iron Fortitude": (
            r"each time a ranged attack targets a heretic astartes unit from your army excluding damned units if the strength characteristic of that attack is greater than the toughness characteristic of that unit subtract 1 from the wound roll",
        ),
        "Tyrannical Motivation": (
            r"in your command phase select one of the following abilities",
            r"until the start of your next command phase each heretic astartes infantry unit from your army has that ability",
            r"at the start of each phase if such a unit is visible to a friendly huron blackheart model until the end of the phase it has both of the following abilities",
            r"each time a model in this unit makes an attack add 1 to the hit roll",
            r"this unit is eligible to shoot and declare a charge in a turn in which it fell back",
            r"if a unit is gaining eligibility to shoot and declare a charge in a turn in which it fell back as a result of being visible to huron blackheart.*unless it is visible again at the start of the respective phase",
        ),
        "Yriel's Own": (
            r"aeldari units in your army are eligible to declare a charge in a turn in which they advanced",
            r"in addition each time an anhrathe rangers or shroud runners unit from your army advances you can reroll the advance roll",
        ),
        "Superior Craftsmanship": (
            r"add \d+ to the range characteristic of ranged weapons equipped by t au empire models from your army",
        ),
        "Killing Blow": (
            r"during the first second and third battle rounds ranged weapons equipped by t au empire models from your army have the assault ability",
            r"during the first second and third battle rounds while a unit is a guided unit its ranged weapons have the lethal hits ability",
        ),
        "Integrated Command Structure": (
            r"kroot and vespid stingwings units from your army have the following ability",
            r"while an enemy unit is within 9 of and visible to this unit each time a ranged attack made by a friendly t au empire model excluding kroot vespid stingwings and titanic models targets that enemy unit improve the armour penetration characteristic of that attack by 1",
            r"t au empire units excluding kroot and vespid stingwings units from your army have the following ability",
            r"while a friendly kroot or vespid stingwings unit is wholly within 6 of and visible to this unit that kroot or vespid stingwings unit can only be selected as the target of a ranged attack if the attacking model is within 18",
        ),
        "Patient Hunter": (
            r"during the third fourth and fifth battle rounds ranged weapons equipped by t au empire models from your army have the sustained hits 1 ability",
            r"during the third fourth and fifth battle rounds while a unit is a guided unit see for the greater good each time a ranged attack is made by a model in that unit that targets a spotted unit you can ignore any or all modifiers to that attacks ballistic skill characteristics and or all modifiers to the hit roll",
        ),
        "Hunter's Instincts": (
            r"each time a kroot model from your army makes an attack add 1 to the hit roll if the target of that attack is below its starting strength and add 1 to the wound roll as well if the target of that attack is below half strength",
        ),
        "Annihilation Protocol": (
            r"each time a destroyer cult or flayed ones unit from your army declares a charge you can reroll the charge roll",
            r"if one or more targets of that charge are below half strength add 1 to the charge roll as well",
            r"each time a destroyer cult unit from your army makes a ranged attack that targets the closest eligible target add 1 to the armour penetration characteristic of that attack",
        ),
        "Command Protocols": (
            r"while a necrons character model is leading this unit each time a model in this unit makes an attack add 1 to the hit roll",
        ),
        "Power Matrix": (
            r"certain areas of the battlefield are considered to be within your armys power matrix as follows",
            r"your deployment zone is always within your armys power matrix",
            r"at the start of any phase if you control at least half of the objective markers within no mans land until the end of that phase no mans land is within your armys power matrix",
            r"at the start of any phase if you control at least half of the objective markers within your opponents deployment zone until the end of that phase your opponents deployment zone is within your armys power matrix",
            r"each time a model in a cryptek or canoptek unit from your army makes an attack reroll a hit roll of 1",
            r"if such a unit is wholly within your armys power matrix you can reroll the hit roll instead",
        ),
        "Technosorcerous Augmentations": (
            r"ranged weapons equipped by cryptek models from your army have the assault ability",
            r"in your shooting phase each time a cryptek unit from your army is selected to shoot select one of the following abilities(?: anti infantry 3 anti mounted 4 assault heavy ignores cover)?",
            r"until the end of the phase ranged weapons equipped by models in that unit have that ability",
        ),
        "Cold Fervour": (
            r"add 2 to the strength characteristic of weapons equipped by destroyer cult models from your army",
            r"the first time each turn that a destroyer cult unit from your army makes attacks that destroy a unit or cause it to become below half strength after that unit has finished resolving its attacks until the end of the turn add 2 to the strength characteristic of weapons equipped by friendly necrons models excluding destroyer cult monster and titanic models",
        ),
        "Hyperphasing": (
            r"at the end of your opponents turn you can select a number of necrons units from your army excluding units that are within engagement range of one or more enemy units",
            r"the maximum number of units you can select depends on the battle size as follows(?: battle size number of units incursion up to 1 units strike force up to 2 units onslaught up to 3 units)?",
            r"once you have made your selections remove those units from the battlefield and place them into strategic reserves",
        ),
        "Worthy Foes": (
            r"in your command phase select one enemy unit",
            r"until the start of your next command phase each time a noble lychguard or triarch unit from your army makes an attack that targets that unit add 1 to the wound roll",
        ),
        "Cosmic Distortion": (
            r"necrons monster units from your army have the following ability",
            r"while an enemy unit is within 6 of this unit it is unravelling",
            r"while an enemy unit is unravelling each time an attack targets that unit improve the armour penetration characteristic of that attack by 1",
            r"at the start of each phase for each necrons monster unit from your army that unit can suffer 3 mortal wounds",
            r"if it does until the end of the phase the range of that units distortion fields aura ability is increased to 9",
            r"if your army contains more than one transcendent c tan unit each of those units must take the reletavistic tether ability",
            r"when mustering your army each necrons monster unit from your army has the relevant necrodermal binding ability shown below and you must increase the points cost of each of those units by the amount shown in the munitorum field manual",
            r"if this causes your army to exceed the points limit for the battle you are playing you cannot include that unit in your army",
        ),
        "Skirmish Fighters": (
            r"kroot models from your army have a 6 invulnerable save against melee attacks and a 5 invulnerable save against ranged attacks",
        ),
        "KEYWORDS": (
            r"(?:if you select this detachment )?.+ units from your army (?:have|gain) the battleline keyword",
        ),
        "Bonded Heroes": (
            r"each time a t au empire battlesuit model from your army makes a ranged attack that targets a unit within 12 improve the strength characteristic of that attack by 1",
            r"if that attack targets a unit within 9 improve the armour penetration characteristic of that attack by 1 as well",
        ),
        "Ruthless Discipline": (
            r"add \d+ to the number of orders each astra militarum officer model from your army can issue as stated on their datasheet",
            r"while an astra militarum unit from your army is affected by an order each time a model in that unit makes an attack reroll a hit roll of \d+",
        ),
        "Only the Best": (
            r"each time an astra militarum infantry model from your army makes a ranged attack reroll a hit roll of \d+",
        ),
        "Fire Zone Purge": (
            r"each time a militarum tempestus model from your army makes a ranged attack in a turn in which it was set up on the battlefield from reserves or it disembarked from a transport add \d+ to the hit roll",
        ),
        "Born Soldiers": (
            r"each time a model in a regiment unit from your army makes a ranged attack that targets a visible unit excluding monsters and vehicles that attack has the lethal hits ability",
            r"each time a model in a squadron unit from your army makes a ranged attack that targets a visible monster or vehicle unit that attack has the lethal hits ability",
        ),
        "Iron Tread": (
            r"each time a squadron unit from your army advances do not make an advance roll for it",
            r"until the end of the phase add \d+ to the move characteristic of models in that unit and when making that advance move that unit can move within engagement range of enemy models but cannot end that move within engagement range of enemy models",
        ),
        "Armoured Fist": (
            r"each time an astra militarum model from your army makes a ranged attack in a turn in which it disembarked from a transport add \d+ to the wound roll",
        ),
        "Masters of Camouflage": (
            r"astra militarum walker and regiment models from your army have the benefit of cover",
            r"while such a model has the benefit of cover for any other reason(?: e)?",
            r"because it is wholly within a ruin improve the save characteristic of that model by \d+ to a maximum of \d+",
        ),
        "Rad-bombardment": (
            r"at the start of the first battle round for each enemy unit within your opponents deployment zone your opponent must decide whether that unit will take cover or stand firm",
            r"you then roll one d6 for each of those enemy units and apply the relevant result below",
            r"on a 3 that unit suffers d3 mortal wounds",
            r"until the end of the battle round that unit is battle shocked and on a 5 that unit suffers d3 mortal wounds",
            r"at the start of your command phase during the second third fourth and fifth battle rounds roll one d6 for each enemy unit within your opponents deployment zone",
            r"on a 3 that unit suffers 1 mortal wound and must take a battle shock test",
        ),
        "Cyber-Psalm Programming": (
            r"add 2 to the move characteristic of models in legio cybernetica units from your army",
            r"(?:in addition )?unless that unit is battle shocked add 1 to the objective control characteristic of models in that unit",
        ),
        "Benedictions Of The Omnissiah": (
            r"at the start of the first battle round select one of the following benedictions of the omnissiah to be active for cult mechanicus units from your army until the end of the battle",
            r"(?:panegyric procession )?each time a cult mechanicus model from your army makes a ranged attack that targets a unit within half range improve the armour penetration characteristic of that attack by 1",
            r"(?:citation in savagery )?each time a cult mechanicus unit from your army is selected to fight if that unit made a charge move this turn until the end of the phase add 1 to the strength and attacks characteristics of melee weapons equipped by models in that unit",
        ),
        "Acquisition At Any Cost": (
            r"at the start of your command phase select one objective marker",
            r"until the start of your next command phase that objective marker is your acquisition objective marker",
            r"each time an adeptus mechanicus model from your army makes an attack if that models unit is within range of your acquisition objective marker or if the target of that attack is within range of your acquisition objective marker reroll a wound roll of 1",
        ),
        "Noospheric Transference": (
            r"in your command phase select one or more adeptus mechanicus units from your army including units that are embarked within transports",
            r"the maximum number of units you can select depends on the battle size as follows",
            r"until the start of your next command phase those units gain the halo override keyword",
            r"then select one of the override abilities below",
            r"until the start of your next command phase units from your army with the halo override keyword have the selected override ability",
            r"add 2 to the move characteristic of models in this unit",
            r"add 1 to the toughness characteristic of models in this unit",
            r"this unit is eligible to declare a charge in a turn in which it advanced",
            r"models in this unit have the stealth ability",
        ),
        "Stealth Optimisation": (
            r"skitarii infantry skitarii mounted and ironstrider ballistarii units from your army have the stealth ability and each time a ranged attack targets a sicarian unit from your army unless the attacking model is within 12 the target has the benefit of cover against that attack",
            r"skitarii infantry skitarii mounted and ironstrider ballistarii units from your army have the stealth ability",
            r"each time a ranged attack targets a sicarian unit from your army unless the attacking model is within 12 the target has the benefit of cover against that attack",
        ),
        "Warp Rifts": (
            r"each time a legiones daemonica unit from your army is set up on the battlefield using the deep strike ability .* it can be set up anywhere that is more than 6 horizontally away from all enemy models instead of more than 9",
        ),
        "Murdercall": (
            r"each time an enemy unit excluding aircraft ends a normal or advance move within 6 of one or more legiones daemonica khorne units from your army one of those legiones daemonica khorne units can make a surge move towards that enemy unit",
            r"to do so roll one d6",
            r"models in your unit move a number of inches up to this result but your unit must end that move as close as possible to that enemy unit",
            r"when doing so those models can be moved within engagement range of that enemy unit",
            r"a unit cannot make a surge move while it is within engagement range of one or more enemy units",
        ),
        "Blood Tainted": (
            r"at the end of a phase in which a legiones daemonica khorne unit from your army destroyed an enemy unit that was within range of an objective marker at the start of the phase if your unit has a higher level of control over that objective marker that objective marker remains under your control until your opponents level of control over that objective marker is greater than yours at the end of a phase",
        ),
        "Beguiling Aura": (
            r"legiones daemonica slaanesh units from your army are eligible to declare a charge in a turn in which they fell back",
        ),
        "Seductive Gambit": (
            r"legiones daemonica slaanesh units from your army have the following ability",
            r"each time this unit ends a charge move you can declare it will perform a seductive gambit",
            r"if you do until the end of the turn this unit does not have the fights first ability but instead each time a model in this unit makes an attack you can reroll the hit roll and you can reroll a wound roll of 1",
        ),
        "Melancholic Miasma": (
            r"while an enemy unit is within 9 of one or more legiones daemonica nurgle units from your army that enemy unit is within your armys shadow of chaos",
            r"in each players command phase select one enemy unit within your armys shadow of chaos",
            r"that unit must take a battle shock test",
        ),
        "Thralls of the First Prince": (
            r"when mustering your army you cannot include any daemon prince daemon prince with wings or epic hero units excluding be lakor but you can include the following heretic astartes units",
            r"the combined points value of such units depends on your battle size as shown below",
            r"incursion up to 500 pts",
            r"strike force up to 1000 pts",
            r"onslaught up to 1500 pts",
            r"be lakor and heretic astartes units from your army gain the shadow legion and undivided keywords",
            r"legiones daemonica units from your army gain the shadow legion keyword",
        ),
        "First Prince of Chaos": (
            r"units from your army have the relevant abilities presented below",
            r"shadow legion khorne units only",
            r"this unit is eligible to shoot and declare a charge in a turn in which it advanced",
            r"shadow legion tzeentch units only",
            r"each time an attack targets this unit subtract 1 from the hit roll",
            r"shadow legion nurgle units only",
            r"each time an attack targets this unit if the strength characteristic of that attack is greater than this units toughness characteristic subtract 1 from the wound roll",
            r"shadow legion slaanesh units only",
            r"enemy units cannot use the fire overwatch stratagem to shoot at this unit",
            r"shadow legion undivided units only",
            r"this unit has the dark pacts army rule and can use it as described in codex.*",
            r"if this unit is be lakor it automatically passes the leadership test required for dark pacts",
            r"shadow legion heretic astartes models in this unit have the deep strike ability",
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
        "Infernal Pacts": (
            r"scintillating legions units from your army have the following the ability",
            r"while a friendly thousand sons psyker unit is within 6 of and visible to this unit models in that unit have a 4 invulnerable save against ranged attacks",
            r"thousand sons units from your army have the following ability",
            r"while a friendly scintillating legions psyker unit is within 6 of and visible to this unit that scintillating legions unit has the cabal of sorcerers ability",
            r"you can include scintillating legions units in your army even though they do not have the thousand sons faction keyword",
            r"the combined points cost of such units you can include in your army is",
            r"incursion up to \d+ pts",
            r"strike force up to \d+ pts",
            r"onslaught up to \d+ pts",
            r"no scintillating legions models from your army can be your warlord",
        ),
        "Flow of Magic": (
            r"certain areas of the battlefield are within your army\s*s flow of magic as follows",
            r"your deployment zone is always within your army\s*s flow of magic",
            r"at the start of any phase if you control at least half of the objective markers within no man\s*s land until the end of that phase no man\s*s land is within your army\s*s flow of magic",
            r"at the start of any phase if you control at least half of the objective markers within your opponent\s*s deployment zone until the end of that phase your opponent\s*s deployment zone is within your army\s*s flow of magic",
            r"each time a thousand sons model from your army makes a psychic attack re\s*roll a wound roll of 1",
            r"if such a model is wholly within your army\s*s flow of magic each time it makes a psychic attack add 1 to the wound roll instead",
        ),
        "Warpfire Infusion": (
            r"each time a thousand sons vehicle unit from your army is selected to shoot or fight apply one of the following when resolving those attacks",
            r"if that vehicle unit is within 6 of one or more friendly thousand sons psyker models you can reroll one hit roll one wound roll and one damage roll",
            r"otherwise you can reroll one hit roll one wound roll or one damage roll",
            r"each time a thousand sons vehicle model from your army with the deadly demise ability is destroyed while it is within 6 of one or more friendly thousand sons psyker models that model(?:s| s) deadly demise ability inflicts mortal wounds on a d6 roll of 5 instead of only a 6",
        ),
        "Warpmeld Sacrifice": (
            r"each time an enemy unit is selected to shoot or fight and one or more tzeentch mutant infantry or tzeentch mutant mounted units from your army are selected as a target of one or more of those attacks each of those tzeentch mutant units can make a warpmeld sacrifice",
            r"if it does until the end of the phase each time an attack targets that unit subtract 1 from the wound roll",
            r"at the end of the phase that tzeentch mutant unit suffers d3 mortal wounds",
            r"each time a tzeentch mutant infantry or tzeentch mutant mounted unit from your army is selected to shoot or fight before selecting its targets that unit can make a warpmeld sacrifice",
            r"if it does until the end of the phase each time a model in that unit makes an attack add 1 to the wound roll",
            r"(?:keywords )?tzaangors units from your army have the battleline keyword and while such a unit is not battle shocked add 1 to the objective control characteristic of tzaangor models in that unit",
            r"tzaangors units from your army have the battleline keyword",
            r"while such a unit is not battle shocked add 1 to the objective control characteristic of tzaangor models in that unit",
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
        "Stitchflesh Abominations": (
            r"each time an attack targets a haemonculus covens unit from your army if the strength characteristic of that attack is greater than the toughness characteristic of your unit subtract 1 from the wound roll",
        ),
        "Murderous Agenda": (
            r"at the start of the first battle round select one of the contracts below then select one unit from your opponents army that matches the contract description in that contract",
            r"until that contract is completed that unit is your contract unit and kabal and blades for hire units from your army have the ability stated in that contract",
            r"at the start of your command phase if your contract unit is destroyed that contract is completed and you gain 3 pain tokens",
            r"at the start of your command phase this contract is completed if all non character models in that unit are destroyed",
            r"each time a kabal or blades for hire model in this unit makes an attack that targets the contract unit that attack has the precision ability",
            r"each time a kabal or blades for hire model in this unit makes an attack that targets an infantry or mounted unit that attack has the sustained hits 1 ability",
            r"each time a kabal or blades for hire model in this unit makes an attack that targets a monster or vehicle unit that attack has the lethal hits ability",
        ),
        "Alliance of Agony": (
            r"at the start of the battle you gain 2 pain tokens for each of the following combinations your army contains these do not need to be in the same attached unit",
        ),
        "Callous Competition": (
            r"at the start of the battle drukhari units from your army are winning the wager",
            r"each time a drukhari unit from your army destroys an enemy unit drukhari units from your army are winning the wager",
            r"each time a harlequins unit from your army destroys an enemy unit harlequin units from your army are winning the wager",
            r"while drukhari units from your army are winning the wager harlequin units from your army are losing the wager and vice versa",
            r"each time a drukhari or harlequins model from your army makes an attack if that models unit is winning the wager reroll a hit roll of 1",
            r"if that models unit is losing the wager reroll a hit roll of 1 and reroll a wound roll of 1 instead",
            r"the combined points cost of such units depends on your battle size",
            r"no harlequins models from your army can be your warlord",
            r"if you select this detachment you cannot use the corsairs and travelling players army rule",
            r"incursion up to 500 pts",
            r"strike force up to 1000 pts",
            r"onslaught up to 1500 pts",
        ),
        "Rain Of Cruelty": (
            r"each time a drukhari unit from your army disembarks from a transport until the end of the turn",
            r"ranged weapons equipped by models in that disembarking unit have the ignores cover ability",
            r"melee weapons equipped by models in that disembarking unit have the lance ability",
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
        "Marked Prey": (
            r"at the start of your command phase select one unit from your opponents army",
            r"until the start of your next command phase each time a war dog model from your army makes an attack that targets that enemy unit if that unit is visible to the attacking model that attack has the sustained hits 1 ability",
            r"while using the houndpack lance detachment the following rules apply",
            r"your army must include three or more war dog units",
            r"war dog units from your army have the battleline keyword",
            r"when mustering your army select three war dog units from your army",
            r"until the end of the battle those units have the character keyword",
            r"this means that the selected units can be given enhancements and one of them can be selected as your warlord",
        ),
        "Dreaded Masters": (
            r"titanic chaos knights units from your army have the following abilities",
            r"while a friendly damned unit is within 9 of this unit each time a model in that unit makes an attack reroll a hit roll of 1 and reroll a wound roll of 1",
            r"chaos knights units from your army have the following abilities",
            r"each time a chaos knights unit with this ability is selected to shoot or fight it can make a dark sacrifice",
            r"if it does select one friendly damned unit within 6",
            r"that damned unit must take a leadership test",
            r"if passed destroy d3 models in that damned unit",
            r"if failed destroy d3 3 models in that damned unit",
            r"in either case then select one of the following abilities for your chaos knights units weapons to have until the end of the phase",
            r"the combined points cost of such units depends on your battle size",
            r"incursion up to 250 pts",
            r"strike force up to 500 pts",
            r"onslaught up to 750 pts",
            r"no damned models from your army can be your warlord",
        ),
        "Tyrannical Court": (
            r"improve the objective control characteristic of chaos knights character models from your army by 2",
            r"(?:in addition )?once per battle round if your warlord is on the battlefield you can use the claimed for the dark gods stratagem for 0cp",
        ),
        "Paragons of Terror": (
            r"at the start of the first battle round after selecting one or more dread abilities to be active for your army you can select one additional dread ability to be active for your army this additional dread ability cannot be randomly selected",
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
        "Acrobatic Onslaught": (
            r"each time a harlequins model from your army makes a charge move it can move through enemy models",
            r"troupe units from your army gain the battleline keyword and troupe models in those units have an objective control characteristic of 2",
        ),
        "Boons of the Brood": (
            r"weapons equipped by harlequins mounted and harlequins vehicle models from your army have the sustained hits \d+ ability",
            r"each time a harlequins unit from your army disembarks from a transport until the end of the turn that units weapons have the sustained hits \d+ ability",
            r"troupe units from your army gain the battleline keyword and troupe models in those units have an objective control characteristic of \d+",
        ),
        "Relentless Raiders": (
            r"while an objective marker is under your control each time an enemy unit ends a normal advance fall back or charge move within range of that objective marker roll one d6",
            r"on a \d+ that enemy unit suffers d3 mortal wounds",
            r"anhrathe units from your army have the following ability",
            r"at the end of a phase if this unit is within range of an objective marker you control that objective marker remains under your control until your opponents level of control over that objective marker is greater than yours at the end of a phase",
        ),
        "Veterans of the Void": (
            r"each time you add an anhrathe unit to your army it can be given up to one corsair enhancement",
            r"each corsair enhancement included in your army must be unique",
            r"if a unit is given a corsair enhancement you must increase the points cost of that unit by the amount shown",
            r"if this causes your army to exceed the points limit for the battle you are playing you cannot include that unit in your army",
        ),
        "Empyric Wellspring": (
            r"each time a unit from your army makes a dark pact select one of the following abilities",
            r"your unit has that ability until the end of the phase",
            r"while this unit is within 9 of one or more friendly heretic astartes psyker models improve the strength characteristic of ranged weapons equipped by models in this unit by \d+",
            r"while this unit is within 9 of one or more friendly heretic astartes daemon prince or a heretic astartes daemon prince with wings models improve the armour penetration characteristic of melee weapons equipped by models in this unit by \d+",
        ),
        "Raiders and Reavers": (
            r"ranged weapons equipped by heretic astartes models from your army have the assault ability and each time a heretic astartes model from your army makes an attack that targets a unit within range of an objective marker improve the armour penetration characteristic of that attack by \d+",
            r"ranged weapons equipped by heretic astartes models from your army have the assault ability",
            r"each time a heretic astartes model from your army makes an attack that targets a unit within range of an objective marker improve the armour penetration characteristic of that attack by \d+",
        ),
        "Slaves to None": (
            r"heretic astartes models from your army lose the dark pacts ability",
            r"ranged weapons equipped by heretic astartes models from your army have the assault ability",
        ),
        "Vendetta": (
            r"at the start of your command phase select one unit from your opponent(?:s| s) army",
            r"until the start of your next command phase that enemy unit is your vendetta target",
            r"each time a heretic astartes model from your army excluding damned models makes an attack that targets your vendetta target you can reroll the hit roll",
        ),
        "Twisted Doctrine": (
            r"in your movement phase each time you set up or select a heretic astartes unit excluding battle shocked units from your army to move it can choose to default to doctrine",
            r"if it does it must first take a battle shock test",
            r"then select one of the following",
            r"until the end of the turn this unit is eligible to shoot and declare a charge in a turn in which it fell back",
            r"until the end of the turn this unit is eligible to declare a charge in a turn in which it advanced",
        ),
        "Debt to the Soul Forge": (
            r"each time a heretic astartes daemon vehicle unit from your army makes a dark pact it can invoke its contract",
            r"if it does subtract \d+ from the resulting leadership test when making that dark pact and until the end of the phase",
            r"each time a model in that unit makes a ranged attack add \d+ to the wound roll",
            r"add \d+ to the attacks characteristic of melee weapons equipped by models in that unit",
        ),
        "Focus of Hatred": (
            r"at the start of your command phase select one unit from your opponent(?:s| s) army to be your focus of hatred",
            r"until the start of your next command phase each time a heretic astartes model from your army excluding damned models makes an attack that targets your focus of hatred you can reroll the hit roll",
        ),
        "Defend at All Costs": (
            r"each time a dire avenger guardian support weapon or war walker model from your army makes an attack if that models unit and or the target unit are within range of one or more objective markers add \d+ to the hit roll",
        ),
        "Strands of Fate": (
            r"at the start of the first battle round you generate fate dice by rolling a number of d6 based on the battle size as shown below",
            r"each time you use one of the stratagems below if your fate dice pool contains one or more fate dice showing the corresponding value in the table below you can discard one of those corresponding fate dice",
            r"ishas fury",
        ),
        "Strength from Death": (
            r"at the end of your opponents shooting phase if one or more ynnari units from your army were destroyed this phase select one ynnari infantry or ynnari mounted unit from your army that was within 6 of your destroyed unit",
            r"once per turn when a ynnari unit from your army performs the fade back agile manoeuvre it can make a lethal surge move instead of a normal move",
            r"if it does roll one d6 and add 1 to the result",
            r"when doing so those models can be moved within engagement range of the enemy unit that just triggered that agile manoeuvre",
            r"at the start of the fight phase select one ynnari unit from your army excluding titanic units that is below its starting strength",
            r"until the end of the phase that unit has the fights first ability",
            r"you can include ynnari units in your army even though they do not have the asuryani faction keyword",
            r"asuryani units excluding epic heroes from your army gain the ynnari keyword",
            r"you must include yvraine and or the yncarne in your army and one of those models must be your warlord",
        ),
        "Extremis-level Threat": (
            r"once per battle in your command phase you can use this ability",
            r"if you do until the start of your next command phase each time a model from your army with the oath of moment ability makes an attack that targets your oath of moment target you can reroll the wound roll as well",
        ),
        "Extremis Sanction": (
            r"officio assassinorum units from your army can use the overkill soulless horror and shieldbreaker abilities twice per battle instead of once per battle but cannot use such an ability more than once in the same battle round",
            r"when mustering your army each officio assassinorum unit from your army has the relevant extremis ability shown on the right and you must increase the points cost of each of those units by the amount shown",
            r"if this causes your army to exceed the points limit for the battle you are playing you cannot include that unit in your army",
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
        "Mailed Fist": (
            r"each time a grey knights vehicle unit from your army advances do not make an advance roll for it",
            r"until the end of the phase add 6 to the move characteristic of models in that unit and until the end of the turn ranged weapons equipped by models in that unit have the assault ability",
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
        "Channelled Force": (
            r"each time a grey knights unit from your army is selected to fight that unit can take a leadership test",
            r"if that test is passed select one of the following rules",
            r"until the end of the phase that unit has that rule",
            r"melee weapons equipped by models in this unit with the psychic ability also have the sustained hits 1 ability",
            r"melee weapons equipped by models in this unit with the psychic ability also have the lethal hits ability",
        ),
        "Prescient Redeployment": (
            r"from the second battle round onwards at the start of your movement phase if you did not select the maximum number of grey knights units from your army using the gate of infinity ability at the end of your opponents previous turn you can select one grey knights unit from your army that is on the battlefield that could have been selected using the gate of infinity ability",
            r"remove that unit from the battlefield and place it into strategic reserves",
            r"this means that your unit can retain its position on the battlefield at the end of your command phase and then be placed into strategic reserves at the start of your movement phase to set it up again in your reinforcements step in another position",
        ),
        "Relentless Onslaught": (
            r"each time a necrons model from your army makes an attack that targets a unit within range of one or more objective markers add \d+ to the hit roll",
            r"in addition ranged weapons equipped by necrons vehicle and necrons mounted models excluding titanic models from your army have the assault ability",
        ),
        "Bold Gallantry": (
            r"each time an imperial knights unit from your army advances until the end of the turn ranged weapons equipped by imperial knights models from your army have the assault ability",
        ),
        "Knightly Teachings": (
            r"each time a model from your army uses its bondsman ability if no other model from your army has used that bondsman ability that turn you can select up to three friendly armiger models instead of one within 12 of that model or within 15 of that model while your army is honoured you still cannot select a model that is already being affected by a bondsman ability",
            r"until the start of your next command phase those models are affected by that bondsman ability",
            r"(?:keywords )?armiger models from your army gain the battleline keyword",
        ),
        "Dauntless Defenders": (
            r"at the start of the first battle round select two objective markers on the battlefield to be your foundations",
            r"when you draw a line from any part of one of your foundations to the other if any part of a model s base or any part of a model s hull for a model without a base crosses that line that model s unit is said to be on your defensive line",
            r"while an imperial knights unit from your army is on your defensive line that unit has the following ability",
            r"against the horde",
            r"each time a model in this unit makes an attack that targets a visible enemy unit you can ignore any or all modifiers to the hit roll",
            r"each time a model in this unit makes an attack that targets a visible enemy unit you can ignore any or all modifiers to the hit roll and weapons equipped by models in this unit have the sustained hits \d+ ability",
            r"weapons equipped by models in this unit have the sustained hits \d+ ability",
            r"each time one of your foundations is removed from the battlefield e",
            r"by a primary mission rule just after it is removed select a new objective marker on the battlefield to be one of your foundations",
            r"each time one of your foundations is removed from the battlefield .* select a new objective marker on the battlefield to be one of your foundations",
        ),
        "Cogbound Alliance": (
            r"imperial knights units from your army have the following the ability",
            r"in your command phase one model in this unit regains 1 lost wound",
            r"if this unit is within 3 of one or more friendly tech priest models one model in this unit regains up to d3 lost wounds instead",
            r"adeptus mechanicus units from your army have the following ability",
            r"each time a model in this unit makes a ranged attack reroll a hit roll of 1",
            r"if this unit is within 6 of one or more friendly imperial knights units reroll a wound roll of 1 as well",
            r"the combined points cost of such units depends on your battle size",
            r"no adeptus mechanicus models from your army can be your warlord",
            r"incursion up to 250 pts",
            r"strike force up to 500 pts",
            r"onslaught up to 750 pts",
        ),
        "Heroes of Legend": (
            r"at the start of your turn if your current oath is fulfilled determine an additional oath as described here with the exception that you cannot select a deed or quality you have already selected if you are randomly selecting the deed and or quality and roll any result that you have already selected select a deed or quality you have not already selected instead",
            r"if you cannot determine an additional oath because you have already selected each deed and each quality do not determine an additional oath",
            r"the qualities from oaths you have fulfilled continue to apply to all models in your army with the code chivalric ability",
            r"when the deed for an additional oath is completed you instead gain 1cp regardless of how you selected the deed or quality",
        ),
        "Valour's Reward": (
            r"you cannot use such enhancements while they are expended",
            r"each time you fulfil your oath each expended enhancement is no longer expended",
        ),
        "Da Boss Is Watchin'": (
            r"at the start of your command phase in a turn in which you have not called a waaagh if you have one or more warboss models on the battlefield or embarked within a transport that is on the battlefield you can call a waaagh for a second time this battle",
            r"when doing so that second waaagh only counts as having been called for warboss nobz and meganobz units from your army",
        ),
        "Da Hunt Is On": (
            r"at the start of your command phase select one monster vehicle or character unit from your opponents army",
            r"until the start of your next command phase that enemy unit is your prey",
            r"each time a beast snagga unit from your army declares a charge that includes your prey as one of the targets you can reroll the charge roll",
            r"each time a beast snagga model from your army makes an attack that targets your prey improve the armour penetration characteristic of that attack by \d+",
        ),
        "Adrenaline Junkies": (
            r"speed freeks units from your army are eligible to shoot and declare a charge in a turn in which they advanced or fell back",
        ),
        "Dakka! Dakka! Dakka!": (
            r"ranged weapons equipped by orks infantry and orks walker models from your army have the assault ability",
            r"while the waaagh is active for your army during your shooting phase ranged weapons equipped by orks infantry and orks walker models from your army have the sustained hits \d+ ability",
        ),
        "Mob Mentality": (
            r"each time an attack targets a boyz unit from your army models in that unit have a \d+ invulnerable save against that attack",
            r"each time an attack targets a boyz unit from your army that contains 10 or more models models in that unit have a \d+ invulnerable save against that attack",
        ),
        "Here Be Loot": (
            r"at the start of the battle round select one objective marker",
            r"until the start of the next battle round that objective marker is your loot objective",
            r"each time a model in an orks infantry orks mounted or orks walker unit from your army makes an attack that attack has the sustained hits \d+ ability if either or both of the following are true",
            r"that model(?: s|s) unit is within range of your loot objective",
            r"that attack targets a unit within range of your loot objective",
        ),
        "Try Dat Button!": (
            r"each time a mek orks walker or grots vehicle unit from your army is selected to shoot or fight roll one d6",
            r"until the end of the phase weapons equipped by models in that unit have the corresponding ability shown in the table below",
            r"sustained hits \d+ ability",
            r"lethal hits ability",
            r"each time an attack is made with this weapon on a critical wound improve the armour penetration characteristic of that attack by \d+",
            r"alternatively when such a unit is selected to shoot or fight you can select one of the abilities above instead of rolling the d6",
            r"if you do until the end of the phase weapons equipped by models in that unit have the hazardous ability as well",
            r"if a weapon equipped by a model from you army has the hazardous ability from multiple sources each time you take a hazardous test for that weapon it is failed on a roll of a \d+ or a \d+",
        ),
        "Lissen ’Ere": (
            r"once per battle round in your command phase or after being set up on the battlefield in your movement phase each boss snikrot mek and warboss model in your army can issue taktiks abilities",
            r"to do so select one of the taktiks abilities below and select one friendly orks unit within 6 of that model to issue them to",
            r"that model must take a leadership test(?: if failed the selected unit suffers 1 mortal wound)?",
            r"if failed the selected unit suffers 1 mortal wound",
            r"until the start of your next command phase the selected unit is affected by the selected taktik",
            r"a unit cannot have taktiks issued to it in this way more than once per battle round",
            r"taktiks abilities cannot be issued to battle shocked units(?: and if a unit affected by taktiks becomes battle shocked all taktiks cease to affect that unit while it is battle shocked)?",
            r"(?:if a unit affected by taktiks becomes battle shocked )?all taktiks cease to affect that unit while it is battle shocked",
            r"(?:get stuck in )?you can reroll charge rolls made for this unit",
            r"(?:get on wiv it )?add 1 to the strength characteristic of melee weapons equipped by models in this unit",
            r"(?:sneaky stalkin )?infantry and mounted models excluding meganobz in this unit have the stealth ability and each time a ranged attack targets this unit those models have the benefit of cover against that attack",
            r"(?:shoota drills )?each time an infantry or mounted model in this unit makes a ranged attack add 1 to the hit roll",
            r"stormboyz units from your army gain the battleline keyword",
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
        "Rapid-drop Deployment": (
            r"at the start of the declare battle formations step select a number of adeptus astartes units excluding titanic units from your army based on the battle size as shown below",
            r"models in those units have the deep strike ability",
            r"each time an adeptus astartes model from your army makes an attack if it was set up on the battlefield this turn reroll a wound roll of \d+",
            r"if it disembarked from a drop pod this turn reroll a hit roll of \d+ as well",
        ),
        "Oath of Reclamation": (
            r"each time an adeptus astartes model from your army makes a melee attack that targets a unit within range of an objective marker improve the armour penetration characteristic of that attack by \d+",
            r"each time an attack targets an adeptus astartes unit from your army if your unit is within range of an objective marker that you controlled at the start of the phase and if the strength characteristic of that attack is greater than the toughness characteristic of your unit or your unit has the titus keyword subtract \d+ from the wound roll",
            r"your army can include ultramarines units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "Purge and Sanctify": (
            r"each time an attack targets an ancient unit from your army if that unit is within range of one or more objective markers and the strength characteristic of that attack is greater than the toughness characteristic of that unit subtract \d+ from the wound roll",
            r"each time a crusader squad unit from your army makes a righteous zeal move that unit can end that move as close as possible to the closest objective marker instead of as close as possible to the closest enemy unit",
            r"your army can include black templars units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "Zealous Litanies": (
            r"at the start of the battle round you can select one of the litanies listed below",
            r"if you do until the end of the battle round that litany is active and its effects apply to all adeptus astartes infantry and adeptus astartes mounted units from your army",
            r"add 2 to the move characteristic of models in this unit and add 1 to advance rolls made for it",
            r"add 1 to the strength characteristic of melee weapons equipped by models in this unit",
            r"models in this unit have a 5 invulnerable save against ranged attacks",
            r"your army can include black templars units but it cannot include(?: any)? adeptus astartes units drawn from any other chapter",
        ),
        "Interlocking Tactics": (
            r"adeptus astartes battleline units from your army are eligible to shoot and declare a charge in a turn in which they advanced or fell back",
            r"are eligible to shoot and declare a charge in a turn in which they advanced or fell back",
            r"are eligible to start to perform an action in a turn in which they advanced or fell back",
            r"each time an adeptus astartes battleline unit from your army is selected to attack after resolving those attacks select one enemy unit hit by one or more of those attacks",
            r"until the end of the turn that enemy unit is auspex scanned",
            r"each time an adeptus astartes model from your army makes an attack that targets an auspex scanned unit reroll a hit roll of \d+",
        ),
        "Lightning Assault": (
            r"adeptus astartes units from your army are eligible to declare a charge in a turn in which they advanced or fell back",
        ),
        "Righteous Fervour": (
            r"you can reroll advance and charge rolls made for adeptus astartes units from your army",
            r"your army can include black templars units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "Masters Of Manoeuvre": (
            r"adeptus astartes units from your army are eligible to shoot in a turn in which they advanced or fell back",
            r"adeptus astartes mounted units from your army are eligible to shoot and declare a charge in a turn in which they advanced or fell back",
            r"your army can include dark angels units but it cannot include any adeptus astartes units drawn from any other chapter",
            r"outrider squad units from your army gain the battleline keyword",
        ),
        "Close-range Eradication": (
            r"ranged weapons equipped by adeptus astartes models from your army have the assault ability",
            r"each time an attack made with such a weapon targets a unit within 12 add \d+ to the strength characteristic of that attack",
            r"ranged weapons equipped by adeptus astartes models from your army have the assault ability and each time an attack made with such a weapon targets a unit within 12 add \d+ to the strength characteristic of that attack",
        ),
        "Storm-swift Onslaught": (
            r"adeptus astartes units from your army are eligible to declare a charge in a turn in which they advanced or fell back",
        ),
        "Wrath of the First Khan": (
            r"at the end of the fight phase if a suboden khan unit from your army destroyed one or more enemy units this phase and is not within engagement range of one or more enemy units that unit can make a normal move of up to \d+",
        ),
        "Red Thirst": (
            r"each time an adeptus astartes unit from your army is selected to fight if that unit made a charge move this turn until the end of the phase add \d+ to the attacks characteristic and add \d+ to the strength characteristic of melee weapons equipped by models in that unit",
            r"your army can include blood angels units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "Shadow Masters": (
            r"each time a ranged attack targets an adeptus astartes unit from your army unless the attacking model is within 12 subtract \d+ from the hit roll and the target has the benefit of cover against that attack",
        ),
        "Masters of Shadow": (
            r"each time a ranged attack targets an adeptus astartes unit from your army unless the attacking model is within 12 subtract \d+ from the hit roll and the target has the benefit of cover against that attack",
        ),
        "Unparalleled Tactician": (
            r"once per battle round if an aethon shaan model from your army is on the battlefield you can use the into darkness stratagem for 0cp",
        ),
        "Restrictions": (
            r"your army can include [a-z0-9 ']+ units but it cannot include(?: any)? adeptus astartes units drawn from any other chapter",
        ),
        "Calculated Annihilation": (
            r"each time a model from your army with the oath of moment ability makes an attack that targets your oath of moment target you can reroll a wound roll of \d+",
        ),
        "Recalculating": (
            r"once per battle round after your oath of moment target is destroyed if a caanok var model from your army is on the battlefield select one enemy unit visible to that model",
            r"that enemy unit becomes your oath of moment target until you select a new one",
        ),
        "Wrath of Dorn": (
            r"each time a model from your army with the oath of moment ability makes an attack that targets your oath of moment target you can reroll a wound roll of \d+",
            r"each time a model in a darnath lysander unit from your army makes an attack that targets your oath of moment target you can reroll the wound roll",
            r"your army can include imperial fists units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "Armoured Wrath": (
            r"once per phase for each adeptus astartes unit in your army you can reroll one hit roll one wound roll or one damage roll made for a model in that unit",
        ),
        "Heroes All": (
            r"each time an adeptus astartes unit from your army is selected to shoot or fight apply one of the following when resolving those attacks",
            r"if your saga is completed see below you can reroll one hit roll one wound roll and one damage roll",
            r"otherwise if that unit is a space wolves character unit you can reroll one hit roll one wound roll or one damage roll",
            r"each time a space wolves character unit from your army does one of the following that unit achieves that boast",
            r"once three or more different boasts have been achieved by units from your army your saga is completed",
            r"that unit destroys your oath of moment target",
            r"that unit destroys your oath of moment target and that is the second oath of moment target destroyed by that unit in this battle",
            r"at the end of either players turn that unit is wholly within your opponents deployment zone",
            r"from the second battle round onwards at the end of your command phase that unit is within range of an objective marker you control that is not within your deployment zone",
        ),
        "Pack's Quarry": (
            r"each time a model in a space wolves unit from your army makes a melee attack that targets an enemy unit if that enemy unit is within engagement range of one or more other adeptus astartes units from your army or if the attacking unit contains more models than that enemy unit",
            r"add \d+ to the hit roll",
            r"if your saga is completed see below add \d+ to the wound roll as well",
            r"at the start of the first battle round your quarry tally is \d+",
            r"each time an adeptus astartes unit from your army fights after all of those attacks have been resolved add \d+ to your quarry tally for each enemy unit destroyed by those attacks",
            r"once your quarry tally is equal to or greater than the number shown in the table below depending on the battle size your saga is completed",
            r"battle size quarry tally incursion \d+ strike force \d+ onslaught \d+",
        ),
        "Master of Wolves": (
            r"at the start of your command phase you can select one of the hunting packs listed below",
            r"until the start of your next command phase that hunting pack is active and its effects apply to all adeptus astartes units from your army",
            r"you can only select each hunting pack once per battle",
            r"this unit can reroll advance rolls and charge rolls",
            r"each time a model in this unit makes a ranged attack add 1 to the hit roll",
            r"each time this unit is selected to fight select either the lethal hits or sustained hits 1 ability",
            r"until the end of the phase weapons equipped by models in this unit have the selected ability",
        ),
        "Howling Onslaught": (
            r"once per battle when selecting a hunting pack for the master of wolves detachment rule if a logan grimnar model from your army is on the battlefield you can select a hunting pack you have already selected this battle",
        ),
        "In The Lion's Claws": (
            r"each time an enemy unit excluding monsters and vehicles within engagement range of one or more ravenwing units from your army falls back all models in that enemy unit must take a desperate escape test",
            r"each time a deathwing unit from your army declares a charge if one or more targets of that charge are within engagement range of one or more ravenwing units from your army add 2 to the charge roll",
            r"your army can include dark angels units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "A Noble Death in Combat": (
            r"each time a death company model from your army makes a melee attack reroll a wound roll of \d+ if that models unit is below its starting strength",
            r"if that models unit is below half strength you can reroll the wound roll instead",
            r"if you select this detachment death company marines and death company marines with bolt rifles units from your army have the battleline keyword",
            r"your army can include blood angels units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "Grim Resolve": (
            r"while an adeptus astartes unit from your army is battle shocked change the objective control characteristic of models in that unit to \d+ instead of \d+",
            r"in your command phase select one adeptus astartes unit from your army",
            r"until the start of your next command phase add \d+ to the objective control characteristic of models in that unit",
            r"your army can include dark angels units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "Vowed Target": (
            r"at the start of your movement phase select one of the following",
            r"select one objective marker you control",
            r"until the start of your next movement phase that objective marker is your vowed objective marker",
            r"select one or more objective markers you do not control",
            r"until the start of your next movement phase each of those objective markers is one of your vowed objective markers",
            r"if a rule refers to a unit or model being within range of your vowed objective marker that rule takes effect if that unit or model is within range of one or more of your vowed objective markers",
            r"each time a deathwing infantry unit from your army makes an attack that targets a unit within range of one or more of your vowed objective markers add 1 to the wound roll",
            r"your army can include dark angels units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "The Great Wolf Watches": (
            r"at the end of your opponents charge phase each adeptus astartes infantry and adeptus astartes walker unit from your army that is within 3 of one or more enemy units and would be eligible to declare a charge against one or more of those units can declare a charge against one or more of those units and you resolve that charge as if it were your charge phase",
            r"if that charge is successful your unit does not receive any charge bonus this turn",
            r"while adeptus astartes terminator units from your army are not battle shocked add 1 to the objective control characteristic of models in those units",
            r"your army can include space wolves units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "Vulkan's Quest": (
            r"ranged weapons equipped by adeptus astartes models from your army have the assault ability and each time an attack made with such a weapon targets a unit within 12 add \d+ to the strength characteristic of that attack",
            r"if your army includes vulkan he\s*stan during your turn each infernus squad unit from your army is eligible to do one of the following",
            r"start to perform an action in a turn in which it advanced",
            r"shoot in a turn in which it started to perform an action",
            r"your army can include salamanders units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "Shock and Awe": (
            r"each time an adeptus astartes unit from your army declares a charge if it disembarked from a transport this turn after selecting the targets of that charge select one of those targets",
            r"that enemy unit must take a battle shock test",
            r"each time a model in an adeptus astartes unit from your army makes a melee attack if it disembarked from a transport this turn add \d+ to the hit roll",
            r"your army can include black templars units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "Mission Tactics": (
            r"at the start of your command phase you can select one of the mission tactics listed below",
            r"until the start of your next command phase that mission tactic is active and its effects apply to all units from your army with this ability",
            r"each mission tactic can only be selected once per battle",
            r"while this mission tactic is active weapons equipped by adeptus astartes units from your army have the sustained hits \d+ ability",
            r"while this mission tactic is active weapons equipped by adeptus astartes units from your army have the lethal hits ability",
            r"while this mission tactic is active each time an adeptus astartes unit from your army makes an attack if a critical hit is scored that attack has the precision ability",
        ),
        "Deathwatch Mission Tactics": (
            r"at the start of your command phase you can select one of the mission tactics listed below",
            r"until the start of your next command phase that mission tactic is active and its effects apply to all deathwatch units from your army",
            r"each mission tactic can only be selected once per battle",
            r"while this mission tactic is active weapons equipped by deathwatch units from your army have the sustained hits \d+ ability",
            r"while this mission tactic is active weapons equipped by deathwatch units from your army have the lethal hits ability",
            r"while this mission tactic is active each time a deathwatch model from your army makes an attack on a critical wound that attack has the precision ability",
        ),
        "Legendary Slayers": (
            r"each time an adeptus astartes model from your army makes an attack if that attack targets a character monster or vehicle unit or if your saga is completed see below that attack has the lethal hits ability",
            r"at the start of the first battle round your beastslayer tally is 0 and you determine your beastslayer target by halving the number of units from your opponents army including those embarked within transports that have one or more of the following keywords rounding up",
            r"each time an adeptus astartes unit from your army shoots or fights after all of those attacks have been resolved add 1 to your beastslayer tally for each enemy unit with one or more of the following keywords destroyed by those attacks",
        ),
        "Psychic Disciplines": (
            r"at the start of the battle round select one of the following psychic disciplines",
            r"until the end of the battle round that psychic discipline is active and its effects apply to all adeptus astartes psyker units from your army",
            r"add 2 to the move characteristic of models in this unit",
            r"each time a model in this unit makes an attack reroll a hit roll of 1 and reroll a wound roll of 1",
            r"each time a ranged attack made by a model in this unit targets an enemy unit within 12 improve the armour penetration characteristic of that attack by 1",
            r"each time a ranged attack targets this unit subtract 1 from the strength characteristic of that attack",
            r"each time a model in this unit makes an attack you can ignore any or all modifiers to that attacks? weapon skill or ballistic skill characteristics and or any or all modifiers to the hit roll",
        ),
        "Maddened Ferocity": (
            r"each time an adeptus astartes model from your army makes a melee attack reroll a wound roll of \d+",
            r"each time an adeptus astartes unit from your army is selected to fight if that unit made a charge move this turn until the end of the phase add \d+ to the attacks characteristic of melee weapons equipped by models in that unit",
            r"if your unit is battle shocked add \d+ to the attacks characteristic of melee weapons equipped by models in that unit instead",
            r"your army can include blood angels units but it cannot include adeptus astartes units drawn from any other chapter",
        ),
        "Legacy of the Angel": (
            r"at the start of the first battle round select two of the angelic legacy abilities listed below",
            r"until the end of the battle those angelic legacy abilities are active and their effects apply to all adeptus astartes character units from your army",
            r"this unit is eligible to shoot and declare a charge in a turn in which it fell back",
            r"each time a model in this unit makes an attack reroll a hit roll of \d+ and reroll a wound roll of \d+",
            r"you can reroll advance and charge rolls made for this unit",
            r"your army can include blood angels units but it cannot include adeptus astartes units drawn from any other chapter",
        ),
        "Upon Wings of Fire": (
            r"at the end of your opponent s turn you can select a number of adeptus astartes jump pack units from your army excluding units that are within engagement range of one or more enemy units",
            r"the maximum number of units you can select depends on the battle size as follows",
            r"battle size units incursion up to \d+ units strike force up to \d+ units onslaught up to \d+ units",
            r"once you have made your selections remove those units from the battlefield and place them into strategic reserves",
            r"in the reinforcements step of your next movement phase set each of those units up using their deep strike ability",
            r"your army can include blood angels units but it cannot include any adeptus astartes units drawn from any other chapter",
        ),
        "Shield of the Imperium": (
            r"ranged weapons equipped by adeptus astartes models from your army have the heavy ability",
            r"if such a weapon already has this ability each time an attack is made with that weapon if the attacking models unit remained stationary this turn add \d+ to the wound roll",
        ),
        "Hyper-adaptations": (
            r"at the start of the first battle round select one of the following hyper adaptations to be active for tyranids units from your army until the end of the battle",
            r"each time a tyranids model with this hyper adaptation makes an attack that targets an infantry or swarm unit that attack has the sustained hits \d+ ability",
            r"each time a tyranids model with this hyper adaptation makes an attack that targets a monster or vehicle unit that attack has the lethal hits ability",
            r"each time a tyranids model with this hyper adaptation makes an attack that targets a character unit on a critical hit that attack has the precision ability",
        ),
        "A Perfect Ambush": (
            r"each time a genestealer cults unit from your army is set up on the battlefield as reinforcements until the end of your next fight phase weapons equipped by models in that unit have the sustained hits \d+ and ignores cover abilities",
        ),
        "Hypermorphic Fury": (
            r"add \d+ to charge rolls made for aberrants biophagus and purestrain genestealers units from your army",
            r"in addition each time such a unit is selected to fight if it made a charge move this turn until the end of the phase add \d+ to the attacks characteristic of melee weapons equipped by models in that unit",
        ),
        "Integrated Tactics": (
            r"each time an astra militarum unit from your army .* is selected to shoot you can select one enemy unit within 18 of and visible to that unit",
            r"(?:if you do )?until the end of the phase models in that astra militarum unit can only target that enemy unit and only if it is an eligible target(?: and that enemy unit is caught in overlapping fire)?",
            r"that enemy unit is caught in overlapping fire",
            r"while an enemy unit is caught in overlapping fire each time a genestealer cults model from your army targets that enemy unit with a ranged attack add 1 to the hit roll",
        ),
        "BROOD BROTHERS": (
            r"you can include astra militarum units in your army even though they do not have the genestealer cults faction keyword",
            r"the combined points cost of such units you can include in your army is",
            r"incursion up to \d+ pts",
            r"strike force up to \d+ pts",
            r"onslaught up to \d+ pts",
            r"a genestealer cults model must be your warlord",
            r"astra militarum models from your army lose the voice of command ability if they have it",
            r"a genestealer cults model must be your warlord and astra militarum models from your army lose the voice of command ability if they have it",
            r"you cannot include units with any of the following keywords in your army using this rule",
        ),
        "Psionic Parasitism": (
            r"at the end of your movement phase for each tyranids synapse unit from your army you can select one friendly genestealer cults unit excluding purestrain genestealer and patriarch units and one friendly tyranids unit each within 9 of and visible to that synapse unit",
            r"if you do that genestealer cults unit from your army suffers d3 1 mortal wounds and one model in the selected tyranids unit regains up to that many lost wounds and until the start of your next movement phase each time a model in the selected tyranids unit makes an attack add 1 to the hit roll",
            r"tyranids units from your army have the following ability",
            r"while an enemy unit is within 6 of this unit each time a friendly genestealer cults unit makes an attack that targets that enemy unit add 1 to the hit roll",
            r"the combined points cost of such units depends on your battle size",
            r"no tyranids models from your army can be your warlord",
            r"incursion up to \d+ pts",
            r"strike force up to \d+ pts",
            r"onslaught up to \d+ pts",
        ),
        "Rapid Takeover": (
            r"while a genestealer cults mounted or genestealer cults vehicle model from your army is not battle shocked add 1 to its objective control characteristic",
            r"in addition at the end of your command phase if one or more atalan jackals units from your army are within range of an objective marker you control that objective marker remains under your control until your opponent(?: s|s) level of control over that objective marker is greater than yours at the end of a phase",
        ),
        "Unquestioning Fanaticism": (
            r"for each acolyte hybrids hybrid metamorphs and neophyte hybrids unit from your army while one or more character models are leading that unit you can reroll advance and charge rolls made for it",
            r"if that character model is a magus primus or acolyte iconward that model has the feel no pain 3 ability while leading that unit",
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
        "Assemblage of Might": (
            r"at the start of your command phase select one unit from your opponent(?: s|s) army",
            r"until the start of your next command phase each time a model in an adeptus custodes character unit from your army makes an attack that targets that enemy unit add 1 to the wound roll",
        ),
        "At all Costs": (
            r"at the start of your command phase you can select one of the following to apply",
            r"select one enemy unit on the battlefield",
            r"until the start of your next command phase each time an agents of the imperium model from your army makes an attack that targets that enemy unit add 1 to the hit roll",
            r"select one objective marker on the battlefield",
            r"until the start of your next command phase while an agents of the imperium unit from your army is within range of that objective marker improve the leadership and objective control characteristics of models in that unit by 1 and models in that unit have a 5 invulnerable save",
        ),
        "Root out Heresy": (
            r"ranged weapons equipped by adeptus arbites inquisitor inquisitorial agents and ordo hereticus models from your army have the ignores cover ability",
            r"each time an adeptus arbites inquisitor inquisitorial agents or ordo hereticus model from your army makes an attack that targets a chaos unit containing 5 or more models that attack has the sustained hits 1 ability",
        ),
        "Destroy the Daemonic": (
            r"each time an inquisitor inquisitorial agents or ordo malleus model from your army makes an attack reroll a hit roll of 1 and if the target of that attack is a daemon unit reroll a wound roll of 1 as well",
        ),
        "Creeping Dread (Aura)": (
            r"in the battle shock step of your opponents command phase if an enemy unit that is either a psyker unit or below its starting strength is within \d+ of one or more anathema psykana models from your army that enemy unit must take a battle shock test",
            r"if that unit is below half strength it must subtract \d+ from its battle shock test this phase instead",
            r"this means that all enemy psyker units within range of this aura ability and all enemy units within range of this aura ability that have lost one or more models must take a battle shock test in your opponents command phase not just those that are below half strength",
        ),
        "Martial Mastery": (
            r"at the start of the battle round you can select one of the bullet points below",
            r"if you do until the start of the next battle round that bullet points effects apply",
            r"each time an adeptus custodes model from your army with the martial ka tah ability makes a melee attack a successful unmodified hit roll of 5 scores a critical hit",
            r"improve the armour penetration characteristic of melee weapons equipped by adeptus custodes models from your army with the martial ka tah ability by 1",
        ),
        "Auric Armour": (
            r"while an adeptus custodes vehicle unit from your army is at starting strength unless that unit is an aircraft or it is battle shocked add 2 to the objective control characteristic of models in that unit",
            r"while an adeptus custodes vehicle unit from your army is below starting strength each time a model in that unit makes an attack reroll a hit roll of 1",
            r"while an adeptus custodes vehicle unit from your army is below half strength each time a model in that unit makes an attack reroll a hit roll of 1 and reroll a wound roll of 1",
            r"moritoi ancients the adeptus custodes honoured fallen are ever eager for battle",
            r"add 2 to the move characteristic of models in adeptus custodes walker units from your army and add 1 to advance and charge rolls made for such units",
            r"(?:keywords )?in the muster armies step you can select up to 2 adeptus custodes walker models from your army",
            r"the selected units gain the character keyword",
            r"this means that the selected models can be given enhancements and one of them can be selected as your warlord",
        ),
        "Revered Companions": (
            r"anathema psykana units from your army gain the following the ability",
            r"while an adeptus custodes unit is within 6 of this unit models in that unit have the feel no pain 5 ability against psychic attacks and mortal wounds",
            r"all other adeptus custodes units from your army gain the following ability",
            r"while an anathema psykana unit is within 6 of this unit each time a model in that anathema psykana unit makes an attack add 1 to the hit roll",
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
        "Mobile Sensor Relays": (
            r"leagues of votann transport units from your army have the following ability",
            r"while a friendly leagues of votann infantry unit is wholly within 6 of this transport ranged weapons equipped by models in that infantry unit have the sustained hits 1 ability",
        ),
        "Fury From The Dêlve": (
            r"cthonian beserks units from your army have the deep strike ability",
            r"cthonian beserks units from your army gain the battleline keyword",
        ),
        "Methodical Annihilation": (
            r"each time a leagues of votann model from your army makes an attack with a weapon that targets the closest eligible target or a target that is within engagement range of that models unit",
            r"reroll a wound roll of \d+",
            r"if your unit is a k hl einhyr hearthguard or thar the destined unit improve the armour penetration characteristic of that attack by \d+",
        ),
        "Martial Leverage": (
            r"each time an enemy unit is destroyed you gain \d+yp",
        ),
        "Optimal Application": (
            r"at the end of your command phase you gain 1yp for each objective marker you control that is not within your deployment zone and has one or more iron master and or memnyr strategist models from your army within range of it to a maximum of 2yp gained from this detachment rule per turn",
            r"in your shooting phase each time a (?:brokhyr|br khyr) ironkin steeljacks or arkanyst evaluator unit from your (?:army|array) is selected to shoot you can spend 1yp",
            r"if you do until the end of the phase each time a model in that unit makes an attack reroll a hit roll of 1",
            r"up to 2 pts",
        ),
        "Ruthless Reinvestment": (
            r"your leagues of votann units do not have the hostile acquisition or fortify takeover abilities except as described in this rule",
            r"at the start of the battle your leagues of votann units have the hostile acquisition ability",
            r"at the end of your command phase you can spend 3yp",
            r"if you do leagues of votann units from your army lose the hostile acquisition ability and gain the fortify takeover ability or vice versa",
        ),
        "Assailed From Every Angle": (
            r"leagues of votann units from your army have the following ability",
            r"guerrilla adepts",
            r"in your shooting phase just after this unit is selected to shoot this unit can use this ability",
            r"if it does select one enemy unit excluding monsters and vehicles",
            r"until the end of the phase attacks made by models in this unit can only target that enemy unit and only if it is an eligible target and after resolving those attacks if one or more of those attacks hit that enemy unit until the start of your next shooting phase that enemy unit is assailed(?: this simply labels that unit for the purposes of this ability and some enhancements and stratagems)?",
            r"if that unit is already assailed until the start of your next shooting phase it is also pinned",
            r"while a unit is pinned subtract \d+ from its move characteristic and subtract \d+ from charge rolls made for it",
        ),
        "Worldblight": (
            r"if you control an objective marker at the end of your command phase and a death guard unit from your army excluding battle shocked units is within range of that objective marker that objective marker remains under your control until your opponents level of control over that objective marker is greater than yours at the end of a phase",
            r"in addition until you lose control of that objective marker it has the nurgles gift ability as if it were a death guard model from your army",
        ),
        "Deadly Vectors": (
            r"in your opponents command phase roll 2d6 for each afflicted enemy unit subtracting 1 from the result if that unit is below half strength",
            r"if the result is 6 or less that enemy unit suffers d3 mortal wounds",
        ),
        "Verminous Haze": (
            r"death guard infantry units excluding poxwalkers units from your army that are not embarked within a transport have the scouts 5 and stealth abilities",
        ),
        "Rush to the Fray": (
            r"each time a world eaters unit from your army disembarks from a transport until the end of the turn add \d+ to charge rolls made for that unit and that units melee weapons have the lance ability",
        ),
        "Trophy Takers": (
            r"the first time this unit destroys an enemy unit until the end of the battle while this unit is not battle shocked add \d+ to the objective control characteristic of models in this unit",
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
        "Feed the Swarm": (
            r"in your command phase each harvester unit from your army can regenerate one friendly tyranids unit that is within 6 of it",
            r"a unit can only be regenerated once per phase",
            r"each time a unit regenerates do one of the following",
            r"one model in that unit regains up to d3 1 lost wounds",
            r"one destroyed infantry model excluding characters is returned to that unit with its full wounds remaining",
            r"if that unit is an endless multitude unit up to 3 destroyed models are returned instead",
        ),
        "Insurmountable Odds": (
            r"each time an enemy unit is selected to shoot after that unit has finished making its attacks if one or more models from one or more endless multitude units from your army were destroyed as a result of those attacks each such unit can make a surge move",
            r"to do so roll one d6",
            r"that unit can be moved a distance in inches up to the result but that unit must end that move as close as possible to the closest enemy unit excluding aircraft",
            r"when doing so those models can be moved within engagement range of enemy units",
            r"a unit cannot make a surge move while it is battle shocked",
        ),
        "Questing Tendrils": (
            r"tyranids units with this ability are eligible to charge in a turn in which they fell back",
            r"vanguard invader units with this ability are eligible to charge in a turn in which they advanced",
        ),
        "Leader-beasts": (
            r"tyranid warriors see below and winged tyranid prime units from your army have a 5 invulnerable save",
            r"(?:keywords )?tyranid warriors with ranged bio weapons and tyranid warriors with melee bio weapons units from your army gain the tyranid warriors and battleline keywords and while such a unit is not battle shocked tyranid warriors models in that unit have an objective control characteristic of 3",
        ),
        "Surprise Assault": (
            r"each time a tyranids model from your army makes an attack reroll a hit roll of \d+",
            r"each time a burrower unit from your army is set up on the battlefield from reserves place a circular \d+mm tunnel marker anywhere on the battlefield within \d+ of that unit and more than \d+ horizontally away from all enemy units",
            r"in the reinforcements step of your movement phase when you set up a unit on the battlefield from reserves you can set that unit up wholly within \d+ of one of your tunnel markers and more than \d+ horizontally away from any enemy units",
            r"if an enemy model excluding aircraft ends any kind of move within \d+ of one of your tunnel markers that tunnel marker is removed from the battlefield",
            r"(?:keywords )?mawloc and trygon units from your army have the burrower keyword",
            r"in the muster armies step you can select up to \d+ trygon models from your army",
            r"the selected units gain the character keyword",
            r"designer s note this means that the selected models can be given enhancements and one of them can be selected as your warlord",
            r"this means that the selected models can be given enhancements and one of them can be selected as your warlord",
        ),
        "Enraged Behemoths": (
            r"each time a tyranids monster model from your army makes an attack add 1 to the hit roll if that model(?: s|s) unit is below its starting strength and add 1 to the wound roll as well if that model(?: s|s) unit is below half strength",
            r"in addition while a tyranids monster unit from your army excluding battle shocked units is at its starting strength add 2 to the objective control characteristic of models in that unit",
        ),
        "Synaptic Imperatives": (
            r"at the start of the battle round you can select one of the synaptic imperatives shown below",
            r"until the end of the battle round that synaptic imperative is active for your army and while a tyranids unit from your army is within synapse range of your army it will benefit from it",
            r"each synaptic imperative can only be selected once per battle",
            r"while this unit is within synapse range of your army models in this unit have a 5 invulnerable save",
            r"while this unit is within synapse range of your army add 1 to advance and charge rolls made for this unit",
            r"while this unit is within synapse range of your army each time a model in this unit makes a melee attack add 1 to the hit roll",
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


def _stratagem_rules_summary(description: str) -> str:
    text = _strip_html(description or "")
    if not text:
        return "-"

    parts: Dict[str, str] = {}
    labels = ("WHEN", "TARGET", "EFFECT")
    for label in labels:
        marker = rf"\b{label}\s*:"
        pattern = rf"{marker}\s*(.*?)(?=(?:\bWHEN\b|\bTARGET\b|\bEFFECT\b|\bRESTRICTIONS?\b)\s*:|$)"
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        value = re.sub(r"\s+", " ", m.group(1)).strip(" .;")
        if value:
            parts[label] = value

    if parts:
        out: List[str] = []
        if "WHEN" in parts:
            out.append(f"When: {parts['WHEN']}.")
        if "TARGET" in parts:
            out.append(f"Target: {parts['TARGET']}.")
        if "EFFECT" in parts:
            out.append(f"Effect: {parts['EFFECT']}.")
        return " ".join(out)

    fallback = re.split(r"\bRESTRICTIONS?\b\s*:", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    return fallback or "-"


def _stratagem_note_block(description: str, status: str, notes: str) -> str:
    return _desc_block(_stratagem_rules_summary(description), _engine_notes(status, notes))


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
        "overcharge": "Hazardous tests for Overcharge profiles apply a -2 roll modifier (raw failures on 1-3).",
        "pistol": "Engaged shooting + pistol-vs-other-ranged choice enforced.",
        "lance": "If the bearer charged this turn, +1 to wound rolls for this weapon.",
        "twin-linked": "Re-roll failed wound rolls for attacks made with this weapon.",
        "precision": "Allows allocating a successful wound to a visible CHARACTER in an Attached unit.",
        "psychic": "Tags Psychic attacks; conditional defenses (FNP/Invulnerable) check this keyword.",
        "psychic assassin": "When targeting a unit with the PSYKER keyword, this weapon's Attacks characteristic becomes 6.",
        "conversion": "Unmodified successful hits of 4+ become critical hits when the target is beyond the Conversion distance.",
        "linked fire": "Linked Fire origin selection supported; range/LOS measured from origin and Attacks=1 override applied.",
        "plasma warhead": "Marker-based fire workflow supported: declaration rules are validated and attacks resolve from the designated marker.",
        "reverberating summons": "Weapon ability: on destroying a model, return 1 Plaguebearer model to a friendly unit within 12\".",
        "c'tan power": "Powers of the C'tan selection limits are enforced when declaring shots.",
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
        "A Perfect Ambush": (
            "Supported",
            "Host of Ascension: each time a GENESTEALER CULTS unit is set up as Reinforcements, its models' weapons gain [SUSTAINED HITS 1] and [IGNORES COVER] until the end of that player's next Fight phase.",
        ),
        "Hypermorphic Fury": (
            "Supported",
            "Biosanctic Broodsurge: ABERRANTS/BIOPHAGUS/PURESTRAIN GENESTEALERS units gain +1 to Charge rolls, and when selected to fight after charging their melee weapons gain +1 Attacks until end of phase.",
        ),
        "Integrated Tactics": (
            "Supported",
            "Brood Brother Auxilia: each time an eligible ASTRA MILITARUM unit is selected to shoot it can optionally select one enemy unit within 18\" and visible (or none); if selected, that ASTRA MILITARUM unit is target-locked to that enemy until end of phase and the enemy is marked as caught in overlapping fire, granting friendly GENESTEALER CULTS ranged attacks +1 to hit against it.",
        ),
        "BROOD BROTHERS": (
            "Supported",
            "Brood Brother Auxilia: ASTRA MILITARUM ally points caps are validated by battle size, forbidden allied keywords are rejected, a GENESTEALER CULTS model must be WARLORD, and allied ASTRA MILITARUM units lose Voice of Command.",
        ),
        "Psionic Parasitism": (
            "Supported",
            "Final Day: end-of-Movement optional SYNAPSE pair selections are queued as deterministic decisions (GENESTEALER CULTS target plus TYRANIDS target, or skip), selected GENESTEALER CULTS units suffer D3+1 mortal wounds, selected TYRANIDS units heal up to that amount and gain +1 to hit until the start of their owner's next Movement phase, TYRANIDS Catalyst aura (+1 to hit for friendly GENESTEALER CULTS attacks vs enemies within 6\") is enforced, and Final Day TYRANIDS ally restrictions/points caps/WARLORD limits are validated.",
        ),
        "Rapid Takeover": (
            "Supported",
            "Outlander Claw: GENESTEALER CULTS MOUNTED and VEHICLE models gain +1 Objective Control while not Battle-shocked, and at the end of your Command phase objective markers you control and that are within range of one or more friendly Atalan Jackals units become sticky until opponent level of control is greater at a phase end.",
        ),
        "Unquestioning Fanaticism": (
            "Supported",
            "Xenocreed Congregation: ACOLYTE HYBRIDS, HYBRID METAMORPHS, and NEOPHYTE HYBRIDS units with one or more attached CHARACTER leaders can re-roll Advance and Charge rolls, and MAGUS/PRIMUS/ACOLYTE ICONWARD leader models in those attached units gain Feel No Pain 3+ while leading.",
        ),
        "Against All Odds": (
            "Supported",
            "Lions of the Emperor: non-vehicle ADEPTUS CUSTODES units gain +1 to hit and +1 to wound when no other friendly units are within 6\" (3D; attached units deduplicated).",
        ),
        "Assemblage of Might": (
            "Supported",
            "Auric Champions: at the start of your Command phase select one enemy unit; until your next Command phase, ADEPTUS CUSTODES Character units gain +1 to wound when targeting that unit.",
        ),
        "Creeping Dread (Aura)": (
            "Supported",
            "Null Maiden Vigil: in your opponent's Command phase, enemy units within 12\" of ANATHEMA PSYKANA models must take Battle-shock tests if they are PSYKER or below Starting Strength; Below Half-strength targets take that test at -1.",
        ),
        "Martial Mastery": (
            "Supported",
            "Shield Host: at the start of each battle round, select one mode (or none) until the next battle round - melee attacks by ADEPTUS CUSTODES models with Martial Ka'tah score critical hits on 5+, or improve AP of those melee weapons by 1.",
        ),
        "Auric Armour": (
            "Supported",
            "Solar Spearhead: ADEPTUS CUSTODES VEHICLE units gain +2 Objective Control at Starting Strength (excluding AIRCRAFT and Battle-shocked units), re-roll Hit rolls of 1 while below Starting Strength, and re-roll Hit rolls of 1 plus Wound rolls of 1 while Below Half-strength; ADEPTUS CUSTODES WALKER units gain +2\" Move and +1 to Advance/Charge rolls; in the Muster Armies step, you can select up to two ADEPTUS CUSTODES WALKER units to gain the CHARACTER keyword.",
        ),
        "Revered Companions": (
            "Supported",
            "Talons Of The Emperor: ANATHEMA PSYKANA units project Null Aegis so nearby ADEPTUS CUSTODES units gain Feel No Pain 5+ against Psychic attacks and mortal wounds, and non-ANATHEMA ADEPTUS CUSTODES units project Deadly Unity so nearby ANATHEMA PSYKANA units gain +1 to Hit.",
        ),
        "Kindred Sorcery": (
            "Supported",
            "Grand Coven: Command-phase selection (once per battle per option) with Imbued Manifestation (+6\" Psychic ranged weapons), Psychic Maelstrom (+1 to wound with Psychic weapons), and Wrath of the Immaterium ([Devastating Wounds] on Psychic weapons).",
        ),
        "Infernal Pacts": (
            "Supported",
            "Changehost of Deceit: Daemonic Illusions grants nearby visible THOUSAND SONS PSYKER units a 4+ invulnerable save against ranged attacks; Mortal Sorcery grants Cabal of Sorcerers to nearby visible SCINTILLATING LEGIONS PSYKER units; Scintillating Legions points caps and WARLORD restriction are validated by battle size.",
        ),
        "Flow of Magic": (
            "Supported",
            "Hexwarp Thrallband: at the start of each phase, Flow zones (own deployment always; No Man's Land/opponent deployment when controlling at least half of those objectives) are snapshotted until phase end; THOUSAND SONS Psychic attacks re-roll Wound rolls of 1, or gain +1 to Wound instead while the attacking model is wholly within Flow of Magic.",
        ),
        "Warpfire Infusion": (
            "Supported",
            "Warpforged Cabal: each time a THOUSAND SONS VEHICLE unit is selected to shoot or fight, Warpfire reroll budget is initialized (near friendly THOUSAND SONS PSYKER model: one Hit, one Wound, and one Damage reroll; otherwise one total reroll among Hit/Wound/Damage); THOUSAND SONS VEHICLE models use Deadly Demise 5+ while within 6\" of a friendly THOUSAND SONS PSYKER model.",
        ),
        "Warpmeld Sacrifice": (
            "Supported",
            "Warpmeld Pact: each time a friendly TZEENTCH MUTANT INFANTRY/MOUNTED unit is selected to shoot or fight it can trigger Warpmeld Sacrifice for +1 to Wound until phase end, and each time such a friendly unit is selected as a target of enemy shooting/fight attacks it can trigger Warpmeld Sacrifice for -1 to enemy Wound rolls until phase end; each activation records an end-of-phase D3 mortal-wound payment; Tzaangors units gain BATTLELINE and TZAANGOR models gain +1 OC while their unit is not Battle-shocked.",
        ),
        "All is Dust": (
            "Supported",
            "Rubricae Phalanx: Rubricae models gain +1 to armour saves against attacks with unmodified Damage 1.",
        ),
        "Mobile Sensor Relays": (
            "Supported",
            "Brandfast Oathband: friendly LEAGUES OF VOTANN INFANTRY units wholly within 6\" of a friendly LEAGUES OF VOTANN TRANSPORT gain [SUSTAINED HITS 1] for ranged weapons.",
        ),
        "Fury From The Dêlve": (
            "Supported",
            "Dêlve Assault Shift: Cthonian Beserks units gain Deep Strike and the BATTLELINE keyword.",
        ),
        "Methodical Annihilation": (
            "Supported",
            "Hearthband: re-roll Wound rolls of 1 when targeting the closest eligible target or a target within Engagement Range; Kahl/Einhyr Hearthguard/Uthar units also improve AP by 1 (attached units inherit this bonus).",
        ),
        "Martial Leverage": (
            "Supported",
            "Needgaârd Oathband: gain 1 Yield Point each time an enemy unit is destroyed (integrates with Prioritised Efficiency).",
        ),
        "Optimal Application": (
            "Supported",
            "Hearthfyre Arsenal: at the end of your Command phase, gain up to 2 YP from controlled non-deployment-zone objectives with Iron-master/Memnyr Strategist models in range; in your Shooting phase, Brôkhyr/Ironkin Steeljacks/Arkanyst Evaluator units can spend 1 YP when selected to shoot to re-roll Hit rolls of 1 until end of phase.",
        ),
        "Ruthless Reinvestment": (
            "Supported",
            "Mercenary Oathband: Prioritised Efficiency no longer auto-switches by YP threshold; at the end of your Command phase you can spend 3 YP to toggle Hostile Acquisition/Fortify Takeover, with mode preserved until you toggle again.",
        ),
        "Assailed From Every Angle": (
            "Supported",
            "Persecution Prospect: in your Shooting phase when a LEAGUES OF VOTANN unit is selected to shoot, it can select one eligible enemy non-MONSTER/non-VEHICLE target (or skip) and attacks are locked to that target for the phase; if one or more attacks hit, the target is assailed until the start of your next Shooting phase, and if it was already assailed it is also pinned (Move -2, Charge -2) until the same timing.",
        ),
        "Worldblight": (
            "Supported",
            "Virulent Vectorium: qualifying objectives become sticky until opponent OC is greater at end of a phase, and remain Nurgle's Gift contagion sources while controlled.",
        ),
        "Deadly Vectors": (
            "Supported",
            "Death Lord's Chosen: in your opponent's Command phase, each Afflicted enemy unit rolls 2D6 (-1 if Below Half-strength), and on 6 or less that unit suffers D3 mortal wounds.",
        ),
        "Manifold Maladies": (
            "Supported",
            "Champions of Contagion: at the start of each battle round, queue an optional Plague selection decision (with None) to replace your active Nurgle's Gift Plague for the rest of the battle.",
        ),
        "Miasmic Bombardment": (
            "Supported",
            "Mortarion's Hammer: at the start of each battle round, select enemy units to become Afflicted if they are more than 12\" from every model in your army on the battlefield (battle-size cap enforced) until end of battle round.",
        ),
        "Numberless Horde": (
            "Supported",
            "Shamblerot Vectorium: in your Command phase, spawn a new Poxwalkers unit at Starting Strength 10 into Strategic Reserves in battle rounds allowed by battle size (2-3 Incursion, 2-4 Strike Force, 2-5 Onslaught), and Poxwalkers units gain Battleline.",
        ),
        "Reverberant Rancidity": (
            "Supported",
            "Tallyband Summoners: PLAGUE LEGIONS units within 7\" of friendly DEATH GUARD units gain Nurgle's Gift as contagion sources, DEATH GUARD units within 7\" of friendly PLAGUE LEGIONS units add 3\" to Contagion Range, PLAGUE LEGIONS ally points caps are enforced by battle size, and PLAGUE LEGIONS units cannot be WARLORD.",
        ),
        "Verminous Haze": (
            "Supported",
            "Flyblown Host: DEATH GUARD INFANTRY units (excluding POXWALKERS) that are not embarked gain Scouts 5\" and Stealth.",
        ),
        "Quicksilver Grace": ("Supported", "Mercurial Host: reroll Advance rolls for eligible units."),
        "Exquisite Swordsmanship": ("Supported", "Peerless Bladesmen: on charge choose Lethal or Sustained for melee."),
        "Empyric Wellspring": (
            "Supported",
            "Cabal of Chaos: each time a unit makes a Dark Pact it also selects Leaping Warpflame or Monstrous Manifestation until end of phase; Leaping Warpflame grants +1 Strength to ranged weapons while within 9\" of a friendly HERETIC ASTARTES PSYKER model, and Monstrous Manifestation grants +1 AP to melee weapons while within 9\" of a friendly HERETIC ASTARTES DAEMON PRINCE source.",
        ),
        "Raiders and Reavers": (
            "Supported",
            "Renegade Raiders: HERETIC ASTARTES ranged weapons count as [ASSAULT], and HERETIC ASTARTES attacks improve AP by 1 when targeting units within range of an objective marker.",
        ),
        "Desperate Devotion": (
            "Supported",
            "Chaos Cult: each time an eligible DAMNED unit with Dark Pacts is selected to move/advance or declare a charge (excluding arrivals from Reserves this turn), it can optionally make a Desperate Pact; on activation, a Leadership test is taken and failed tests inflict D3 mortal wounds, then the unit gains +2 Move and +2 to Charge rolls until end of phase.",
        ),
        "Experimental Augmentations": (
            "Supported",
            "Creations of Bile: at the start of battle, select one augmentation or roll two D6 (with optional Fabius Bile rerolls); duplicate results do not stack, and eligible HERETIC ASTARTES INFANTRY models excluding DAMNED gain the selected Move/Toughness/WS/BS/Attacks/Strength bonuses for the battle.",
        ),
        "Masters of Misdirection": (
            "Supported",
            "Deceptors: in the Declare Battle Formations step, select eligible LEGIONARIES/CULTIST MOB units (battle-size caps enforced per unit type); selected units gain Infiltrators until end of battle, and attached non-EPIC HERO CHARACTER units also gain Infiltrators while attached.",
        ),
        "Terror Descends (Aura)": (
            "Supported",
            "Dread Talons: in the Battle-shock step of your opponent's Command phase, below-Starting Strength enemy units within 12\" of friendly HERETIC ASTARTES sources are forced to take a Battle-shock test, affected units are flagged to suppress further Battle-shock tests in that phase, and in-range Battle-shock tests use the detachment's -1 test modifier support.",
        ),
        "Terror Made Manifest": (
            "Supported",
            "Nightmare Hunt: in the Battle-shock step of your opponent's Command phase, below-Starting Strength enemy units within 12\" of friendly HERETIC ASTARTES sources are forced to take a Battle-shock test at -1 and are marked to suppress further tests in that phase; HERETIC ASTARTES attacks gain +1 to hit vs Below Half-strength targets and +1 to wound vs Battle-shocked targets, and attacks made by Battle-shocked models suffer -1 to hit against friendly HERETIC ASTARTES units.",
        ),
        "Marks of Chaos": (
            "Supported",
            "Pactbound Zealots: eligible HERETIC ASTARTES non-EPIC HERO units are assigned a roster mark (defaulting to CHAOS UNDIVIDED when unspecified), Dark Pact success enables mark-specific bonuses (+critical hits on 5+ for KHORNE/TZEENTCH/NURGLE/SLAANESH attack types and re-roll Hit rolls of 1 for CHAOS UNDIVIDED), and restrictions are enforced for KHORNE PSYKER selection plus leader/bodyguard and transport/passenger shared marks.",
        ),
        "Iron Fortitude": (
            "Supported",
            "Fellhammer Siege-host: each time a ranged attack targets a friendly HERETIC ASTARTES unit (excluding DAMNED), if the attack Strength is greater than that unit's Toughness, subtract 1 from the Wound roll.",
        ),
        "Tyrannical Motivation": (
            "Supported",
            "Huron's Marauders: in your Command phase choose Huron's Elite (+1 to hit for HERETIC ASTARTES INFANTRY) or Mobile Marauders (shoot/charge after Falling Back for HERETIC ASTARTES INFANTRY) until your next Command phase; at each phase start, units visible to a friendly Huron Blackheart gain both abilities for that phase.",
        ),
        "Slaves to None": (
            "Supported",
            "Renegade Warband: HERETIC ASTARTES units from your army lose access to Dark Pacts, and ranged weapons equipped by HERETIC ASTARTES models from your army gain [ASSAULT].",
        ),
        "Vendetta": (
            "Supported",
            "Renegade Warband: at the start of your Command phase, select one enemy unit as your Vendetta target until your next Command phase; HERETIC ASTARTES models from your army (excluding DAMNED) can re-roll Hit rolls when attacking that target.",
        ),
        "Twisted Doctrine": (
            "Supported",
            "Renegade Warband: in your Movement phase, each time an eligible HERETIC ASTARTES unit is set up or selected to move it can take a Battle-shock test and choose one mode until end of turn (shoot/charge after Falling Back, or charge after Advancing).",
        ),
        "Debt to the Soul Forge": (
            "Supported",
            "Soulforged Warpack: each time an eligible HERETIC ASTARTES DAEMON VEHICLE unit makes a Dark Pact it can invoke its contract; invoked contracts apply -1 to the resulting Leadership test and, until end of phase, grant +1 to wound for ranged attacks and +2 Attacks to melee weapons for that unit.",
        ),
        "Focus of Hatred": (
            "Supported",
            "Veterans of the Long War: at the start of your Command phase, select one enemy unit as your Focus of Hatred until your next Command phase; HERETIC ASTARTES models from your army (excluding DAMNED) can re-roll Hit rolls when attacking that target.",
        ),
        "Mechanised Murder": ("Supported", "Rapid Evisceration: reroll Hit/Wound rolls of 1 for eligible units."),
        "Daemonic Empowerment": (
            "Supported",
            "Carnival of Excess: empowered units gain Sustained Hits 1; if a weapon already has Sustained Hits, its unmodified hit rolls of 5+ score Critical Hits.",
        ),
        "Skilled Crews": (
            "Supported",
            "Armoured Warhost: AELDARI VEHICLE ranged weapons count as [ASSAULT]; AELDARI VEHICLE FLY units can re-roll Advance rolls.",
        ),
        "Superior Craftsmanship": (
            "Supported",
            "Experimental Prototype Cadre: add 6\" to the Range characteristic of ranged weapons equipped by T'AU EMPIRE models from your army.",
        ),
        "Killing Blow": (
            "Supported",
            "Mont'ka: during battle rounds 1-3, ranged weapons of T'AU EMPIRE models count as [ASSAULT], and while a unit is Guided its ranged weapons gain [LETHAL HITS].",
        ),
        "Integrated Command Structure": (
            "Supported",
            "Auxiliary Cadre: KROOT/VESPID spotters grant +1 AP to eligible friendly T'AU EMPIRE ranged attacks against visible enemies within 9\", and KROOT/VESPID units wholly within 6\" and visible to eligible friendly T'AU EMPIRE sources can only be targeted by ranged attacks from within 18\".",
        ),
        "Patient Hunter": (
            "Supported",
            "Kauyon: battle rounds 3-5 grant [SUSTAINED HITS 1] to ranged weapons of T'AU EMPIRE models; guided attacks targeting spotted units can ignore any/all Ballistic Skill modifiers and/or any/all Hit roll modifiers.",
        ),
        "Hunter's Instincts": (
            "Supported",
            "Kroot Hunting Pack: KROOT models gain +1 to hit against targets below starting strength and gain +1 to wound as well against targets below half-strength.",
        ),
        "Skirmish Fighters": (
            "Supported",
            "Kroot Hunting Pack: KROOT models gain a 6+ invulnerable save against melee attacks and a 5+ invulnerable save against ranged attacks.",
        ),
        "Bonded Heroes": (
            "Supported",
            "Retaliation Cadre: T'AU EMPIRE BATTLESUIT models gain +1 Strength on ranged attacks against targets within 12\", and those attacks also gain +1 AP against targets within 9\".",
        ),
        "Path of the Warrior": (
            "Supported",
            "Aspect Host: select re-roll Hit 1s or re-roll Wound 1s each time an Aspect Warriors or Avatar of Khaine unit is selected to shoot or fight (until end of phase).",
        ),
        "Acrobatic Onslaught": (
            "Supported",
            "Ghosts of the Webway: Harlequins units can move through enemy models when making Charge moves; Travelling Players grants BATTLELINE and OC 2 to Troupe units/models, and Death Jester/Shadowseer/Troupe Master caps are set to 3 each.",
        ),
        "Boons of the Brood": (
            "Supported",
            "Serpent's Brood: HARLEQUINS MOUNTED and HARLEQUINS VEHICLE models gain [SUSTAINED HITS 1], HARLEQUINS units that disembark from a TRANSPORT gain [SUSTAINED HITS 1] until end of turn, and Travelling Players grants BATTLELINE/OC 2 to Troupe units/models with Death Jester/Shadowseer/Troupe Master caps set to 3 each.",
        ),
        "Yriel's Own": (
            "Supported",
            "Eldritch Raiders: AELDARI units can charge in turns in which they Advanced; ANHRATHE, RANGERS, and SHROUD RUNNERS units can re-roll Advance rolls.",
        ),
        "Relentless Raiders": (
            "Supported",
            "Corsair Coterie: when an enemy unit ends a Normal/Advance/Fall Back/Charge move within range of an objective you control, roll D6 and on 2+ that unit suffers D3 mortal wounds; ANHRATHE units also apply Void Thieves sticky objective control at phase end.",
        ),
        "Veterans of the Void": (
            "Supported",
            "Corsair Coterie/Eldritch Raiders: ANHRATHE units can take detachment Corsair Enhancements (including non-Character units), Corsair Enhancements remain unique, enhancement points are included in unit cost, and enhancement cap scales with ANHRATHE units.",
        ),
        "Defend at All Costs": (
            "Supported",
            "Guardian Battlehost: Dire Avengers, Guardians, Support Weapon, and War Walker models gain +1 to hit if their unit and/or the target unit is within range of one or more objective markers.",
        ),
        "Strands of Fate": (
            "Supported",
            "Seer Council: first battle round generates Fate dice by battle size (Incursion 3, Strike Force 6, Onslaught 9); when using Presentiment of Dread/Forewarned/Unshrouded Truth/Fate Inescapable/Isha's Fury/Psychic Shield, you can discard a matching Fate die (1-6) to reduce that stratagem's CP cost by 1.",
        ),
        "Strength from Death": (
            "Supported",
            "Devoted of Ynnead: Lethal Intent target selection at end of opponent Shooting phase with D6+1 reactive move, once-per-turn Lethal Surge Fade Back upgrade allowing movement within Engagement Range of the triggering enemy, Lethal Reprisal Fight phase selection granting Fights First, and Servants of the Whispering God army restrictions.",
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
        "Feed the Swarm": (
            "Supported",
            "Assimilation Swarm: in your Command phase, each eligible HARVESTER queues an optional CHOOSE_QUARRY regeneration decision (with None), then either heals one friendly TYRANIDS model by D3+1 or returns destroyed INFANTRY non-CHARACTER models (up to 3 for ENDLESS MULTITUDE); source/target per-phase limits are enforced, including Regenerating Monstrosity and Biophagic Flow range interactions.",
        ),
        "Insurmountable Odds": (
            "Supported",
            "Unending Swarm: after each enemy unit finishes shooting, each ENDLESS MULTITUDE unit from your army that lost models from those attacks can make a reactive Surge move by rolling D6 and moving up to that distance; the move must end as close as possible to the closest non-AIRCRAFT enemy unit, can enter Engagement Range, and is blocked while Battle-shocked.",
        ),
        "Questing Tendrils": (
            "Supported",
            "Vanguard Onslaught: TYRANIDS units can declare charges in turns when they Fell Back, and TYRANIDS units with the VANGUARD INVADER keyword can also declare charges in turns when they Advanced.",
        ),
        "Leader-beasts": (
            "Supported",
            "Warrior Bioform Onslaught: Tyranid Warriors with Ranged/Melee Bio-weapons gain TYRANID WARRIORS and BATTLELINE; TYRANID WARRIORS models in those units have Objective Control 3 (Battle-shock core rule still sets OC to 0); TYRANID WARRIORS and WINGED TYRANID PRIME units gain a 5+ invulnerable save.",
        ),
        "Surprise Assault": (
            "Supported",
            "Subterranean Assault: TYRANIDS models re-roll Hit rolls of 1; MAWLOC/TRYGON units gain BURROWER; each BURROWER unit set up from Reserves queues mandatory Tunnel Marker placement (within 1\" of that unit and more than 3\" from enemy units); Reinforcements setups can instead be wholly within 9\" of a Tunnel Marker and more than 6\" from enemies; enemy non-AIRCRAFT units ending any move within 3\" remove those markers; in Muster Armies, select up to two TRYGON units to gain CHARACTER.",
        ),
        "Enraged Behemoths": (
            "Supported",
            "Crusher Stampede: TYRANIDS MONSTER models gain +1 to Hit while their unit is below Starting Strength and +1 to Wound while their unit is Below Half-strength; TYRANIDS MONSTER units that are at Starting Strength and not Battle-shocked gain +2 Objective Control.",
        ),
        "Synaptic Imperatives": (
            "Supported",
            "Synaptic Nexus: at the start of each battle round, optionally select one unused Synaptic Imperative (or none) via CHOOSE_QUARRY; selected imperative applies to TYRANIDS units within Synapse Range for that round only, granting either a 5+ invulnerable save, +1 to Advance and Charge rolls, or +1 to melee Hit rolls. Each imperative can only be selected once per battle.",
        ),
        "Da Boss Is Watchin'": (
            "Supported",
            "Bully Boyz: after your first Waaagh!, a second Command phase Waaagh! can be called if a Warboss model is on the battlefield (including embarked in a battlefield Transport); that second Waaagh! only affects WARBOSS, Nobz, and Meganobz units.",
        ),
        "Da Hunt Is On": (
            "Supported",
            "Da Big Hunt: at the start of your Command phase, select an enemy MONSTER, VEHICLE, or CHARACTER as your Prey until your next Command phase; BEAST SNAGGA units can re-roll Charge rolls when declaring charges that include that Prey, and BEAST SNAGGA model attacks improve AP by 1 against that Prey.",
        ),
        "Adrenaline Junkies": (
            "Supported",
            "Kult of Speed: SPEED FREEKS units are eligible to shoot and declare a charge in turns when they Advanced or Fell Back.",
        ),
        "Dakka! Dakka! Dakka!": (
            "Supported",
            "More Dakka!: ORKS INFANTRY/WALKER ranged weapons count as ASSAULT, and while Waaagh! is active during your Shooting phase those models' ranged attacks gain Sustained Hits 1.",
        ),
        "Mob Mentality": (
            "Supported",
            "Green Tide: each time an attack targets a BOYZ unit from your army, models in that unit gain a 6+ invulnerable save against that attack, improving to 5+ while that unit contains 10 or more models.",
        ),
        "Here Be Loot": (
            "Supported",
            "Freebooter Krew: at the start of each battle round select one objective marker as your Loot objective via CHOOSE_QUARRY; ORKS INFANTRY/MOUNTED/WALKER model attacks gain Sustained Hits 1 while the attacker's unit is within range of that objective and/or while targeting a unit within range of that objective.",
        ),
        "Try Dat Button!": (
            "Supported",
            "Dread Mob: each time an eligible Mek/Walker/Grots Vehicle unit is selected to shoot or fight, choose roll/manual effect via CHOOSE_QUARRY; effects apply until phase end (Sustained Hits 1, Lethal Hits, or AP +2 on Critical Wound), manual selection also grants Hazardous, and multiple Hazardous sources fail on 1-2.",
        ),
        "Lissen ’Ere": (
            "Supported",
            "Taktikal Brigade: each Boss Snikrot/Mek/Warboss model can issue one once-per-battle-round Taktik choice (or none) in your Command phase or after Reinforcements setup in your Movement phase; selected friendly ORKS unit within 6\" takes a Leadership test for the issuing model (failure inflicts 1 mortal wound) and gains one Taktik until your next Command phase (Get Stuck In charge re-rolls, Get On Wiv It +1 melee Strength, Sneaky Stalkin' Stealth + model-level Benefit of Cover excluding Meganobz, Shoota Drills +1 ranged hit for INFANTRY/MOUNTED models), with Battle-shock gating and Stormboyz gaining Battleline.",
        ),
        "Get Stuck In": ("Supported", "War Horde: ORKS melee weapons gain Sustained Hits 1."),
        "Combat Doctrines": ("Supported", "Gladius Task Force: select each doctrine once per battle to grant move/charge eligibility."),
        "Extremis-level Threat": (
            "Supported",
            "1st Company Task Force: once per battle optional Command phase activation grants full Wound re-rolls against the current Oath of Moment target until your next Command phase.",
        ),
        "Extremis Sanction": (
            "Supported",
            "Veiled Blade Elimination Force: OFFICIO ASSASSINORUM units gain one additional use each for Overkill/Soulless Horror/Shieldbreaker (max once per battle round per ability), and Callidus/Culexus/Eversor/Vindicare unit costs include the detachment surcharges (+40/+40/+35/+45).",
        ),
        "Mastered Doctrines": (
            "Supported",
            "Blade of Ultramar: up to three Command phase doctrine selections; doctrine reuse requires Marneus Calgar on the battlefield; doctrine effects and Ultramarines-only chapter restriction enforced.",
        ),
        "Rapid-drop Deployment": (
            "Supported",
            "Orbital Assault Force: at Declare Battle Formations select battle-size-scaled non-TITANIC ADEPTUS ASTARTES units to gain Deep Strike, and ADEPTUS ASTARTES attacks re-roll Wound rolls of 1 if set up this turn plus re-roll Hit rolls of 1 if disembarked from a Drop Pod this turn.",
        ),
        "Oath of Reclamation": (
            "Supported",
            "Reclamation Force: ADEPTUS ASTARTES melee attacks improve AP by 1 against targets within objective range, and attacks targeting your ADEPTUS ASTARTES units suffer -1 to wound when those units are within objective range of markers controlled at phase start and either Strength exceeds Toughness or the unit has TITUS; Ultramarines-only chapter restriction enforced.",
        ),
        "Purge and Sanctify": (
            "Supported",
            "Vindication Task Force: attacks targeting your ADEPTUS ASTARTES ANCIENT units suffer -1 to wound while those units are within objective range and the attack Strength exceeds their Toughness, and ADEPTUS ASTARTES CRUSADER SQUAD units can end Righteous Zeal moves as close as possible to the closest objective marker instead of the closest enemy unit; Black Templars-only chapter restriction enforced.",
        ),
        "Zealous Litanies": (
            "Supported",
            "Wrathful Procession: at the start of each battle round you can optionally select one litany (or none); Chorus of Relentless Hate grants ADEPTUS ASTARTES INFANTRY/MOUNTED units +2\" Move and +1 to Advance rolls, Rite of Perfervid Wrath grants +1 Strength to melee weapons, and Chant of Deathless Devotion grants a 5+ invulnerable save against ranged attacks; Black Templars-only chapter restriction enforced.",
        ),
        "Interlocking Tactics": (
            "Supported",
            "Bastion Task Force: ADEPTUS ASTARTES BATTLELINE units can shoot/charge and start Actions after Advancing or Falling Back, and after such a unit resolves attacks it selects one hit enemy as auspex scanned until end of turn, granting ADEPTUS ASTARTES attacks re-roll Hit rolls of 1 against that unit.",
        ),
        "Lightning Assault": (
            "Supported",
            "Stormlance Task Force: ADEPTUS ASTARTES units can declare charges in turns when they Advanced or Fell Back.",
        ),
        "Righteous Fervour": (
            "Supported",
            "Companions of Vehemence: ADEPTUS ASTARTES units can re-roll Advance and Charge rolls; Black Templars-only chapter restriction enforced.",
        ),
        "Masters Of Manoeuvre": (
            "Supported",
            "Company of Hunters: ADEPTUS ASTARTES units can shoot after Advancing/Falling Back, ADEPTUS ASTARTES MOUNTED units can also charge after Advancing/Falling Back, Dark Angels chapter restriction enforced, and Outrider Squad units gain Battleline.",
        ),
        "Close-range Eradication": (
            "Supported",
            "Firestorm Assault Force: ADEPTUS ASTARTES ranged weapons count as [ASSAULT], and attacks with those weapons gain +1 Strength against targets within 12\".",
        ),
        "Storm-swift Onslaught": (
            "Supported",
            "Spearpoint Task Force: ADEPTUS ASTARTES units can declare charges in turns when they Advanced or Fell Back.",
        ),
        "Wrath of the First Khan": (
            "Supported",
            "Spearpoint Task Force: at the end of the Fight phase, eligible Suboden Khan units that destroyed enemy units this phase and are no longer engaged can make a Normal move up to 6\".",
        ),
        "Red Thirst": (
            "Supported",
            "Liberator Assault Group: ADEPTUS ASTARTES units that charged gain +1 Attacks and +2 Strength for melee weapons when selected to fight until end of phase; Blood Angels-only chapter restriction enforced.",
        ),
        "Shadow Masters": (
            "Supported",
            "Vanguard Spearhead: ranged attacks targeting ADEPTUS ASTARTES units from more than 12\" away suffer -1 to hit, and those targets gain the Benefit of Cover.",
        ),
        "Masters of Shadow": (
            "Supported",
            "Shadowmark Talon: ranged attacks targeting ADEPTUS ASTARTES units from more than 12\" away suffer -1 to hit, and those targets gain the Benefit of Cover.",
        ),
        "Unparalleled Tactician": (
            "Supported",
            "Shadowmark Talon: once per battle round, if Aethon Shaan is on the battlefield, you can use INTO DARKNESS for 0CP.",
        ),
        "Calculated Annihilation": (
            "Supported",
            "Hammer of Avernii: attacks by ADEPTUS ASTARTES models against the current Oath of Moment target can re-roll Wound rolls of 1.",
        ),
        "Recalculating": (
            "Supported",
            "Hammer of Avernii: once per battle round, after the Oath target is destroyed and while Caanok Var is on the battlefield, queue a visible-enemy selection that becomes the new Oath of Moment target.",
        ),
        "Wrath of Dorn": (
            "Supported",
            "Emperor's Shield: attacks by ADEPTUS ASTARTES models against the current Oath of Moment target can re-roll Wound rolls of 1, and Darnath Lysander units can re-roll the Wound roll instead.",
        ),
        "Armoured Wrath": (
            "Supported",
            "Ironstorm Spearhead: once per phase, each ADEPTUS ASTARTES unit can re-roll one Hit roll, one Wound roll, or one Damage roll.",
        ),
        "Heroes All": (
            "Supported",
            "Saga of the Bold: pre-Saga Space Wolves CHARACTER units gain one selected-to-shoot/fight re-roll choice (Hit, Wound, or Damage), and once three Boasts are achieved the Saga is complete so selected ADEPTUS ASTARTES units gain one Hit, one Wound, and one Damage re-roll; Boast tracking covers Oath target kills (including second kill by the same unit), end-of-turn wholly-in-opponent-deployment-zone checks, and end-of-own-Command-phase controlled non-home objective checks.",
        ),
        "Master of Wolves": (
            "Supported",
            "Saga of the Great Wolf: Command-phase Hunting Pack selection with once-per-pack tracking, Encircling Jaws (Advance/Charge re-rolls), Hunter's Eye (+1 ranged hit), and Ferocious Strike fight-time choice between Lethal Hits and Sustained Hits 1.",
        ),
        "Howling Onslaught": (
            "Supported",
            "Saga of the Great Wolf: once per battle, when Logan Grimnar is on the battlefield, a previously selected Hunting Pack can be selected again.",
        ),
        "In The Lion's Claws": (
            "Supported",
            "Lion's Blade Task Force: enemy non-MONSTER/non-VEHICLE units Falling Back while within Engagement Range of your RAVENWING units are forced to take Desperate Escape tests with an additional -1 when Battle-shocked, and DEATHWING units gain +2 to Charge rolls when charging targets within Engagement Range of one or more friendly RAVENWING units; Dark Angels-only chapter restriction enforced.",
        ),
        "A Noble Death in Combat": (
            "Supported",
            "The Lost Brethren: Death Company units re-roll Wound rolls of 1 in melee while below Starting Strength and re-roll the Wound roll instead while below Half-strength; Death Company Marines and Death Company Marines with Bolt Rifles units gain Battleline.",
        ),
        "Grim Resolve": (
            "Supported",
            "Unforgiven Task Force: while Battle-shocked, ADEPTUS ASTARTES units have Objective Control 1 instead of 0, and in each Command phase you select one ADEPTUS ASTARTES unit to gain +1 Objective Control until your next Command phase.",
        ),
        "Vowed Target": (
            "Supported",
            "Inner Circle Task Force: at the start of your Movement phase, select Defensive Footing (one controlled objective marker) or Aggressive Push (one or more uncontrolled objective markers), track selected Vowed objective marker(s) until your next Movement phase, and grant +1 to wound for DEATHWING INFANTRY attacks that target units within range of one or more Vowed objective markers; Dark Angels-only chapter restriction enforced.",
        ),
        "The Great Wolf Watches": (
            "Supported",
            "Champions of Fenris: at the end of the opponent Charge phase, eligible ADEPTUS ASTARTES INFANTRY/WALKER units within 3\" of enemy units can declare out-of-turn charges that do not receive the Charge bonus, and ADEPTUS ASTARTES TERMINATOR units gain +1 Objective Control while not Battle-shocked; Space Wolves-only chapter restriction enforced.",
        ),
        "Vulkan's Quest": (
            "Supported",
            "Forgefather's Seekers: ranged weapons for ADEPTUS ASTARTES units count as [ASSAULT], gain +1 Strength within 12\", and while Vulkan He'stan is on the battlefield Infernus Squad units can start Actions after Advancing and can shoot in turns they started an Action; Salamanders-only chapter restriction enforced.",
        ),
        "Shock and Awe": (
            "Supported",
            "Godhammer Assault Force: when an eligible ADEPTUS ASTARTES unit that disembarked from a TRANSPORT declares a charge, select one declared charge target to take a Battle-shock test, and that charging unit's melee attacks gain +1 to hit this turn; Black Templars-only chapter restriction enforced.",
        ),
        "Mission Tactics": (
            "Supported",
            "Black Spear Task Force: in each Command phase you can select one unchosen Mission Tactic for the battle round; Furor grants Sustained Hits 1, Malleus grants Lethal Hits, and Purgatus grants Precision on critical hits for ADEPTUS ASTARTES units until your next Command phase.",
        ),
        "Legendary Slayers": (
            "Supported",
            "Saga of the Beastslayer: BR1 Beastslayer target tally setup (including embarked CHARACTER/MONSTER/VEHICLE enemy units), post-shoot/fight kill tally tracking, Saga completion state, and conditional Lethal Hits are implemented.",
        ),
        "Pack's Quarry": (
            "Supported",
            "Saga of the Hunter: BR1 Quarry tally setup by battle size (Incursion 2, Strike Force 3, Onslaught 4), fight-sequence enemy-unit kill tally tracking for ADEPTUS ASTARTES units, and Space Wolves melee +1 to hit with conditional +1 to wound once the Saga is completed when outnumbering the target or when another friendly ADEPTUS ASTARTES unit is engaging that target.",
        ),
        "Psychic Disciplines": (
            "Supported",
            "Librarius Conclave: start-of-battle-round discipline selection (Biomancy, Divination, Pyromancy, Telekinesis, Telepathy) with ADEPTUS ASTARTES PSYKER gating, including +2 Move, re-roll Hit/Wound rolls of 1, AP improvement within 12\", incoming ranged Strength reduction by 1, and optional ignore-negative WS/BS/Hit modifiers handling.",
        ),
        "Legacy of the Angel": (
            "Supported",
            "Angelic Inheritors: start-of-first-battle-round selection of exactly two Angelic Legacy abilities (Sanguinary Grace, Carmine Wrath, Their Appointed Hour) with Character-unit gating, plus Blood Angels chapter restriction enforcement.",
        ),
        "Upon Wings of Fire": (
            "Supported",
            "The Angelic Host: at the end of your opponent turn, select up to battle-size cap eligible ADEPTUS ASTARTES JUMP PACK units (Incursion 1, Strike Force 2, Onslaught 3) not in Engagement Range to enter Strategic Reserves, then force next-turn Movement-phase Deep Strike arrival windows for selected units.",
        ),
        "Shield of the Imperium": (
            "Supported",
            "Anvil Siege Force: all ADEPTUS ASTARTES ranged weapons count as [HEAVY], and weapons that already have [HEAVY] gain +1 to wound while their unit remained stationary.",
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
        "Stitchflesh Abominations": (
            "Supported",
            "Covenite Coterie: each time an attack targets a friendly HAEMONCULUS COVENS unit, if the attack Strength is greater than that unit's Toughness, subtract 1 from the Wound roll.",
        ),
        "Murderous Agenda": (
            "Supported",
            "Kabalite Cartel: at the start of the first battle round, select Trophy Hunters, Sow Fear and Terror, or Show of Strength and an eligible enemy Contract unit; while active, KABAL/BLADES FOR HIRE attacks gain the contract keyword effect (Precision vs Contract target, Sustained Hits 1 vs INFANTRY/MOUNTED, or Lethal Hits vs MONSTER/VEHICLE), and at the start of your Command phase the contract completes when its condition is met and grants 3 Pain tokens.",
        ),
        "Alliance of Agony": (
            "Supported",
            "Realspace Raiders: at the start of the battle, gain 2 Pain tokens for each present pair (Archon+Kabalite Warriors, Succubus+Wyches, Haemonculus+Wracks), cumulative to a maximum of 6.",
        ),
        "Callous Competition": (
            "Supported",
            "Reaper's Wager: start with DRUKHARI winning, switch winner when DRUKHARI or HARLEQUINS units from your army destroy enemy units, apply re-roll Hit rolls of 1 for winning units and re-roll Hit/Wound rolls of 1 for losing units, and enforce HARLEQUINS ally-only caps (Incursion 500, Strike Force 1000, Onslaught 1500), HARLEQUINS WARLORD prohibition, and Corsairs and Travelling Players incompatibility.",
        ),
        "Rain Of Cruelty": (
            "Supported",
            "Skysplinter Assault: each time a friendly DRUKHARI unit disembarks from a Transport, mark that unit until end of turn so its ranged weapons gain [IGNORES COVER] and its melee weapons gain [LANCE].",
        ),
        "Malefic Surge": (
            "Supported",
            "Infernal Lance: Command-phase unit selection with Leadership test + D3 mortals on failure; Empowered state grants Unholy Hunger (+3\" Move), Diabolic Power (Lethal or Sustained Hits 1), or Unnatural Fortitude (5+ invuln or FNP 6+), then consumes Empowered.",
        ),
        "Marked Prey": (
            "Supported",
            "Houndpack Lance: command-phase enemy-unit selection grants [SUSTAINED HITS 1] to visible WAR DOG attacks against that target until your next Command phase; validates minimum three WAR DOG units, grants BATTLELINE to WAR DOG units, and enforces selection of exactly three WAR DOG units to gain CHARACTER during Muster Armies.",
        ),
        "Dreaded Masters": (
            "Supported",
            "Iconoclast Fiefdom: Dread Tyrants aura grants DAMNED units within 9\" of friendly TITANIC CHAOS KNIGHTS re-roll Hit and Wound rolls of 1; Dark Sacrifice prompts once each time a CHAOS KNIGHTS unit is selected to shoot/fight to choose a friendly DAMNED unit within 6\" and either [LETHAL HITS] or [SUSTAINED HITS 1] until end of phase after destroying D3 (or D3+3 on failed Leadership) models; Wretched Thralls enforces DAMNED ally points cap by battle size and blocks DAMNED Warlords.",
        ),
        "Tyrannical Court": (
            "Supported",
            "Lords of Dread: Chaos Knights CHARACTER models gain +2 Objective Control, and once per battle round, if your Warlord is on the battlefield, you can use CLAIMED FOR THE DARK GODS for 0CP.",
        ),
        "Paragons of Terror": (
            "Supported",
            "Traitoris Lance: at the start of battle round 1, after Harbingers selection resolves, queue an optional additional non-random Dread ability selection (or None).",
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
        "Mailed Fist": (
            "Supported",
            "Sanctic Spearhead: GREY KNIGHTS VEHICLE units replace Advance rolls with a fixed +6\" Move equivalent and "
            "their ranged weapons count as [ASSAULT] for that turn after Advancing.",
        ),
        "Channelled Force": (
            "Supported",
            "Banishers: each time an eligible GREY KNIGHTS unit is selected to fight, choose None or a Leadership-test option; "
            "on a passed test, psychic melee weapons gain either [LETHAL HITS] or [SUSTAINED HITS 1] until end of phase.",
        ),
        "Prescient Redeployment": (
            "Supported",
            "Augurium Task Force: from battle round 2 onward at the start of your Movement phase, if fewer than the Gate of Infinity max units were selected at the end of the opponent's previous turn, choose one eligible GREY KNIGHTS unit to enter Strategic Reserves.",
        ),
        "Warp Rifts": (
            "Supported",
            "Daemonic Incursion: Deep Strike min distance reduced to 6\" when wholly within Shadow of Chaos zones or within 6\" of a matching Greater Daemon/Dark Master aura; cannot bootstrap off the arriving unit.",
        ),
        "Murdercall": (
            "Supported",
            "Blood Legion: enemy Normal/Advance move endings within 6\" of eligible KHORNE LEGIONES DAEMONICA units queue a reactive unit selection; selected unit rolls D6 and makes a Surge move (as close as possible to the trigger unit), and may move into Engagement Range while not already engaged.",
        ),
        "Blood Tainted": (
            "Supported",
            "Blood Legion: phase-start objective-range snapshots plus kill tracking identify eligible destroyed enemies; at phase end, destroying KHORNE LEGIONES DAEMONICA units apply sticky control on qualifying objectives when their Level of Control is higher.",
        ),
        "Beguiling Aura": (
            "Supported",
            "Legion of Excess: eligible SLAANESH LEGIONES DAEMONICA units can declare charges in turns in which they Fell Back.",
        ),
        "Seductive Gambit": (
            "Supported",
            "Legion of Excess: charge-end optional Seductive Gambit decision toggles off Fights First until end of turn while granting melee re-roll Hit and re-roll Wound rolls of 1.",
        ),
        "Melancholic Miasma": (
            "Supported",
            "Plague Legion: enemy units within 9\" of eligible NURGLE LEGIONES DAEMONICA units count as within your Shadow of Chaos; each Command phase queues a deterministic enemy-unit selection in your Shadow of Chaos to take a Battle-shock test.",
        ),
        "Thralls of the First Prince": (
            "Supported",
            "Shadow Legion: muster validation enforces Daemon Prince/non-Be'lakor Epic Hero bans, allows only listed HERETIC ASTARTES or DAMNED picks, applies battle-size points caps, and applies SHADOW LEGION/UNDIVIDED keyword grants.",
        ),
        "First Prince of Chaos": (
            "Supported",
            "Shadow Legion: MURDERER'S COWL advance-and-shoot/charge, PENUMBRAL PUPPETRY -1 to hit, GLOAM ROT -1 to wound when Strength exceeds Toughness, SHADOW'S CARESS no Overwatch targeting, and DISCIPLES OF BE'LAKOR Dark Pacts with Be'lakor auto-pass plus SHADOW LEGION HERETIC ASTARTES Deep Strike are implemented.",
        ),
        "Fates in Flux": (
            "Supported",
            "Scintillating Legion: Flux tokens tracked and transferable; TZEENTCH LEGIONES DAEMONICA units can spend tokens for Advance/Hit/Wound/Save/Damage/Hazardous re-rolls (multi-die selections supported), opponents can spend tokens on Advance/Hit/Wound/Save re-rolls unless they also have Fates in Flux, and Command phase token gain applies when the opponent has tokens.",
        ),
        "Martial Grace": ("Supported", "Warhost: +1 Battle Focus token; Swift as the Wind +1\" move; +1 to D6 Agile Manoeuvre rolls."),
        "Ride the Wind": (
            "Supported",
            "Windrider Host: ASURYANI MOUNTED/VYPER units can be allocated to Reserves and are treated as Strategic Reserves for setup timing/rules, gain +1 effective battle round when setting up from Strategic Reserves, and can be selected at end of the opponent turn (Incursion 1, Strike Force 2, Onslaught 3) to enter Strategic Reserves; Windriders gain BATTLELINE.",
        ),
        "Shepherds of the Dead": (
            "Supported",
            "Spirit Conclave: each destroyed ASURYANI PSYKER model grants a Vengeful Dead token to the enemy unit that destroyed it; WRAITH CONSTRUCT models gain +1 hit/+1 wound against tokened units; Spirit Guides aura grants Battle Focus to nearby Wraithblades/Wraithguard/Wraithlord units; Wraithblades and Wraithguard gain BATTLELINE.",
        ),
        "Bold Gallantry": (
            "Supported",
            "Valourstrike Lance: IMPERIAL KNIGHTS ranged weapons count as [ASSAULT] when checking Advance-and-shoot eligibility.",
        ),
        "Knightly Teachings": (
            "Supported",
            "Spearhead-At-Arms: first use each turn of a given Bondsman ability can target up to three eligible friendly ARMIGER units, later uses of that same Bondsman ability that turn are restricted to one target, target range is 12\" (15\" while Honoured), already-affected Bondsman targets are excluded, and ARMIGER units gain BATTLELINE.",
        ),
        "Dauntless Defenders": (
            "Supported",
            "Gate Warden Lance: start-of-first-battle-round selection of two foundation objective markers defines a defensive line; IMPERIAL KNIGHTS units on that line gain [SUSTAINED HITS 1] and can ignore Hit roll modifiers against visible targets, and removed foundations prompt deterministic replacement objective selection.",
        ),
        "Cogbound Alliance": (
            "Supported",
            "Questor Forgepact: Command phase Sacristan Pledge heals one lost wound for each IMPERIAL KNIGHTS unit (D3 while within 3\" of a friendly TECH-PRIEST), ADEPTUS MECHANICUS units gain Divine Inspiration re-roll Hit rolls of 1 for ranged attacks with re-roll Wound rolls of 1 while within 6\" of friendly IMPERIAL KNIGHTS units, and Forge World ally list/points cap/warlord restrictions are validated.",
        ),
        "Heroes of Legend": (
            "Supported",
            "Questoris Companions: when a current Code Chivalric Oath is fulfilled, start-of-turn Heroes of Legend automatically prepares and queues additional Deed/Quality oath selection using deterministic CHOOSE_CHIVALRIC_OATH flow, prevents re-selecting previously used Deeds/Qualities (including random-roll duplicates), preserves fulfilled Oath Qualities as cumulative active effects, and grants +1CP when each additional Oath Deed is completed.",
        ),
        "Valour’s Reward": (
            "Supported",
            "Questoris Companions: Valour's Reward expended-state tracking is provided for listed detachment enhancements (expended enhancements are blocked via manager state), and every time a Code Chivalric Oath is fulfilled all expended enhancement states are cleared.",
        ),
        "Annihilation Protocol": (
            "Supported",
            "Annihilation Legion: DESTROYER CULT and FLAYED ONES units can re-roll Charge rolls; declared charges get +1 when any target is Below Half-strength; DESTROYER CULT ranged attacks improve AP by 1 against the closest eligible target.",
        ),
        "Power Matrix": (
            "Supported",
            "Canoptek Court: start-of-phase Power Matrix snapshot (own deployment zone always; No Man's Land and opponent deployment zone active when controlling at least half of their objective markers), CRYPTEK/CANOPTEK units re-roll Hit rolls of 1, and those units re-roll the Hit roll instead while wholly within the Power Matrix.",
        ),
        "Technosorcerous Augmentations": (
            "Supported",
            "Cryptek Conclave Technosorcerous Augmentations: CRYPTEK models' ranged weapons count as Assault for Advance-and-shoot eligibility, and in your Shooting phase each selected CRYPTEK unit prompts a deterministic choice of ANTI-INFANTRY 3+, ANTI-MOUNTED 4+, ASSAULT, HEAVY, or IGNORES COVER, applying the chosen keyword to that unit's ranged weapons until phase end.",
        ),
        "Cold Fervour": (
            "Supported",
            "Cursed Legion Cold Fervour: weapons equipped by DESTROYER CULT models gain +2 Strength, and the first time each turn a DESTROYER CULT unit destroys a unit or causes one to become Below Half-strength after finishing its attacks, eligible friendly NECRONS non-DESTROYER CULT/non-MONSTER/non-TITANIC models gain +2 Strength until turn end.",
        ),
        "Hyperphasing": (
            "Supported",
            "Hypercrypt Legion Hyperphasing: at the end of your opponent's turn, eligible NECRONS units not in Engagement Range can be selected (battle-size cap: Incursion 1, Strike Force 2, Onslaught 3) and moved into Strategic Reserves via deterministic multi-select decision flow.",
        ),
        "Worthy Foes": (
            "Supported",
            "Obeisance Phalanx Worthy Foes: in your Command phase, select one enemy unit; until your next Command phase, NOBLE/LYCHGUARD/TRIARCH units from your army gain +1 to Wound rolls when attacking that selected unit.",
        ),
        "Cosmic Distortion": (
            "Supported",
            "Pantheon of Woe Cosmic Distortion: NECRONS MONSTER units project Distortion Fields (enemy units within 6\" are unravelling and attacks targeting them improve AP by 1), and at the start of each phase you can select any eligible friendly NECRONS MONSTER units to suffer 3 mortal wounds to extend their Distortion Fields range to 9\" until phase end via deterministic multi-select decision flow. Necrodermal Binding surcharge validation is applied for Pantheon mustering.",
        ),
        "Relentless Onslaught": ("Supported", "Starshatter Arsenal: +1 to hit vs targets within objective range; VEHICLE/MOUNTED (non-TITANIC) ranged weapons gain Assault."),
        "Ruthless Discipline": (
            "Supported",
            "Grizzled Company: OFFICERs issue +1 order; ordered units re-roll Hit rolls of 1.",
        ),
        "Only the Best": (
            "Supported",
            "Bridgehead Strike: ASTRA MILITARUM INFANTRY models re-roll Hit rolls of 1 for ranged attacks.",
        ),
        "Fire Zone Purge": (
            "Supported",
            "Bridgehead Strike: MILITARUM TEMPESTUS models gain +1 to hit for ranged attacks on turns they were set up from Reserves or disembarked from a Transport.",
        ),
        "Born Soldiers": (
            "Supported",
            "Combined Arms: visible REGIMENT ranged attacks gain Lethal Hits versus non-MONSTER/non-VEHICLE targets, and visible SQUADRON ranged attacks gain Lethal Hits versus MONSTER/VEHICLE targets.",
        ),
        "Iron Tread": (
            "Supported",
            "Hammer of the Emperor: SQUADRON units replace Advance rolls with a fixed +6\" and can move within (but not end within) Engagement Range during that Advance move.",
        ),
        "Armoured Fist": (
            "Supported",
            "Mechanised Assault: ASTRA MILITARUM models gain +1 to wound on ranged attacks in turns they disembarked from a Transport.",
        ),
        "Masters of Camouflage": (
            "Supported",
            "Recon Element: ASTRA MILITARUM WALKER and REGIMENT models gain Benefit of Cover against ranged attacks, and while they already have cover from another source their Save characteristic improves by 1 (to a maximum of 3+).",
        ),
        "Artillery Support": (
            "Supported",
            "Siege Regiment: at the start of each battle round, select Creeping Barrage, Incendiary Bombardment, or Smoke Shells; Creeping Barrage rolls for each eligible enemy unit more than 12\" from every friendly on-battlefield model and applies Shaken (Move -2\", Charge -2) up to battle-size caps (Incursion 2, Strike Force 3, Onslaught 4), Incendiary Bombardment selects eligible enemy units up to that cap to become Scattered (cannot have Benefit of Cover), and Smoke Shells selects friendly units up to that cap to gain Stealth until the end of the battle round.",
        ),
        "Rad-bombardment": (
            "Supported",
            "Rad-Zone Corps: BR1 Bombardment prompts the opponent to choose Stand Firm or Take Cover per enemy unit in their deployment zone, resolves mortal wounds by threshold, applies Take Cover Battle-shock until end of battle round, and BR2-5 Fallout applies 1 mortal wound plus a Battle-shock test on 3+ (Radial Suffusion extends Fallout targeting to enemy units within 6\" of their deployment zone while the bearer is on the battlefield).",
        ),
        "Cyber-Psalm Programming": (
            "Supported",
            "Cohort Cybernetica: models in friendly LEGIO CYBERNETICA units gain +2\" Move, and while their unit is not Battle-shocked they gain +1 Objective Control.",
        ),
        "Benedictions Of The Omnissiah": (
            "Supported",
            "Data-Psalm Conclave: at the start of battle round 1 you select Panegyric Procession or Citation in Savagery; Panegyric improves AP by 1 for CULT MECHANICUS ranged attacks within half range, and Citation grants CULT MECHANICUS charged units +1 Strength and +1 Attacks for melee weapons while resolving fight attacks.",
        ),
        "Acquisition At Any Cost": (
            "Supported",
            "Explorator Maniple: in your Command phase you select one objective marker as your Acquisition objective until your next Command phase, and ADEPTUS MECHANICUS attacks re-roll Wound rolls of 1 while either the attacker or target unit is within range of that selected objective marker.",
        ),
        "Noospheric Transference": (
            "Supported",
            "Haloscreed Battle Clade: in your Command phase you select units for HALO OVERRIDE based on battle size (Incursion 1, Strike Force 2, Onslaught 3), then select one override ability; Electromotive gives +2\" Move, Microactuator gives +1 Toughness, Predation allows charging after Advancing, and Muted grants Stealth until your next Command phase.",
        ),
        "Stealth Optimisation": (
            "Supported",
            "Skitarii Hunter Cohort: SKITARII INFANTRY/SKITARII MOUNTED and IRONSTRIDER BALLISTARII units gain Stealth, and SICARIAN units gain Benefit of Cover against ranged attacks unless the attacking model is within 12\".",
        ),
        "The Blood of Martyrs": (
            "Supported",
            "Hallowed Martyrs: ADEPTA SORORITAS models gain +1 to hit below Starting Strength and +1 to wound below Half-strength.",
        ),
        "Sacred Rites": (
            "Supported",
            "Army of Faith: ADEPTA SORORITAS units can perform up to two Acts of Faith per phase instead of one.",
        ),
        "Fervent Purgation": (
            "Supported",
            "Bringers of Flame: ADEPTA SORORITAS ranged weapons count as Assault and gain +1 Strength against targets within 6\".",
        ),
        "Righteous Purpose": (
            "Supported",
            "Champions of Faith: at each of your Command phases, choose up to 3 ADEPTA SORORITAS units to become Righteous until your next Command phase (+1\" Move, Leadership improves by 1, and Battle Sisters Squad/Celestian Sacresants/Paragon Warsuits weapons improve WS/BS by 1); CELESTIAN SACRESANTS models also gain +1 Objective Control while their unit is not Battle-shocked.",
        ),
        "Desperate for Redemption": (
            "Supported",
            "Penitent Host: at the start of each battle round, optionally select one unused Vow of Atonement (or none) for your army; The Path of the Penitent grants PENITENT models +3\" Move, Absolution in Battle grants PENITENT models +1 Attacks and +1 Strength for melee weapons while their unit charged this turn, and Death Before Disgrace grants PENITENT models melee fight-on-death on 2+ after the attacker finishes its attacks.",
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
        "A Character unit can only be attached to a unit if both units share the same keyword from the list above.": (
            "Supported",
            "Pactbound Zealots: attachment validation and attach action checks require matching Marks of Chaos between leader and bodyguard units.",
        ),
        "A unit can only embark within (or start the battle embarked within) a TRANSPORT if both of those units share the same keyword from the list above.": (
            "Supported",
            "Pactbound Zealots: embark validation and transport eligibility checks require matching Marks of Chaos between transport and passenger units.",
        ),
        "You cannot select the KHORNE keyword for a Psyker unit.": (
            "Supported",
            "Pactbound Zealots: KHORNE is rejected for PSYKER units during detachment validation and mark resolution.",
        ),
        "When mustering your army, each NECRONS MONSTER unit from your army has the relevant Necrodermal Binding ability shown below, and you must increase the points cost of each of those units by the amount shown in the Munitorum Field Manual . If this causes your army to exceed the points limit for the battle you are playing, you cannot include that unit in your army.": (
            "Supported",
            "Pantheon of Woe Necrodermal Binding surcharges are enforced in unit point costs for NECRONS MONSTER units, so army points-limit validation includes the mandatory Pantheon binding costs.",
        ),
        "You can include the BLOOD LEGIONS units in your army. The combined points cost of such units you can include in your army is: Incursion: Up to 500 pts Strike Force: Up to 1000 pts Onslaught: Up to 1500 pts No BLOOD LEGIONS model from your army can be your WARLORD.": (
            "Supported",
            "BLOOD LEGIONS points caps enforced by battle size; BLOOD LEGIONS cannot be your WARLORD.",
        ),
        "You can include Scintillating Legions units in your army, even though they do not have the THOUSAND SONS Faction keyword. The combined points cost of such units you can include in your army is: Incursion: Up to 500 pts Strike Force: Up to 1000 pts Onslaught: Up to 1500 pts No SCINTILLATING LEGIONS models from your army can be your WARLORD .": (
            "Supported",
            "SCINTILLATING LEGIONS points caps are enforced by battle size; SCINTILLATING LEGIONS cannot be your WARLORD.",
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
        ("DG", "Grotesque Regeneration"): (
            "Supported",
            "End of each phase: each damaged Beasts of Nurgle model regains all lost wounds.",
        ),
        ("CD", "Chance for Glory"): (
            "Supported",
            "Once per battle, start of Fight phase: improve S/A/AP/D of the bearer's melee weapons by 1 until end of phase.",
        ),
        ("CD", "Despoilers"): ("Supported", "After making a Dark Pact, unit re-rolls Hit rolls until end of phase."),
        ("CD", "Unholy Bloodshed"): (
            "Supported",
            "Once per battle, when making a Dark Pact, unit weapons gain [DEVASTATING WOUNDS] until end of phase.",
        ),
        ("CD", "Malign Sacrifice"): (
            "Supported",
            "Start of Fight phase: select a Dark Disciple and an enemy within Engagement Range, roll D6 (2-5=1 MW, 6=D3 MW) and destroy the Disciple.",
        ),
        ("CD", "Sacrificial Dagger"): (
            "Supported",
            "Once per phase on being selected to shoot or fight: unit suffers 1 MW; bearer gains +1 to hit/wound with Psychic attacks until end of phase.",
        ),
        ("CD", "Gift of Chaos (Psychic)"): (
            "Supported",
            "After resolving attacks, select a unit hit by the bearer's Psychic attacks to take a Leadership test or suffer D3 MW.",
        ),
        ("CD", "Death Hex (Psychic)"): (
            "Supported",
            "Start of Shooting: select a visible enemy within 12\"; roll D6 (1: Psyker unit suffers D3 MW; 2+: attacks vs target improve AP by 1) until next Movement phase.",
        ),
        ("CD", "Demagogue"): (
            "Supported",
            "Once per battle, start of any phase: select a Battle-shocked friendly HERETIC ASTARTES unit within 12\" of a DARK APOSTLE model to clear Battle-shock.",
        ),
        ("CSM", "Demagogue"): (
            "Supported",
            "Once per battle, start of any phase: select a Battle-shocked friendly HERETIC ASTARTES unit within 12\" of a DARK APOSTLE model to clear Battle-shock.",
        ),
        ("CSM", "Fleet Command"): (
            "Supported",
            "After deployment, if source (or embarked transport) is on the battlefield, redeploy up to three HERETIC ASTARTES units and optionally place them into Strategic Reserves regardless of limits.",
        ),
        ("CSM", "Plunder"): (
            "Supported",
            "Once per battle after a Normal move: optional visible enemy within 12\"; roll D6 and on 2+ it suffers D3+1 mortal wounds.",
        ),
        ("CSM", "Choice Samples"): (
            "Supported",
            "Command phase single choice while Garreon the Corpsemaster is alive: return one destroyed non-CHARACTER model to this unit or gain 1CP if a friendly HERETIC ASTARTES INFANTRY unit within 3\" is below Starting Strength.",
        ),
        ("CD", "Tally of Pestilence"): (
            "Supported",
            "Track enemy models destroyed by NURGLE LEGIONES DAEMONICA units; at the start of your Command phase if tally >= 7, gain 1CP and reset the tally.",
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
        ("DRU", "Devoted to Pain"): (
            "Supported",
            "If equipped with two macro-scalpels, those weapons gain [TWIN-LINKED].",
        ),
        ("DRU", "Eradicate the Foe"): (
            "Supported",
            "Hit rerolls against targets at Starting Strength are applied for both full-reroll and reroll-1 variants.",
        ),
        ("DRU", "Onslaught"): (
            "Supported",
            "Leading: pile-in and consolidation moves can move up to 6\" instead of 3\".",
        ),
        ("DRU", "Shadowfield"): (
            "Supported",
            "Bearer cannot re-roll invulnerable saves; first failed invulnerable save removes the invulnerable save for the rest of the battle.",
        ),
        ("DRU", "Silent Executioner"): (
            "Supported",
            "Re-roll Hit rolls vs targets below Starting Strength; re-roll Wound rolls vs targets below Half-strength.",
        ),
        ("DRU", "Soul Trap"): (
            "Supported",
            "Bearer melee weapons gain +1 Attacks/+1 Strength, increasing to +2 Attacks/+2 Strength after the first melee kill resolves.",
        ),
        ("DRU", "Thrilling Spectacle"): (
            "Supported",
            "Once per battle, start of Fight phase optional activation: bearer gains a 3+ invulnerable save and sets melee weapon Attacks to 12 until end of phase.",
        ),
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
        ("DG", "Deluge of Nurgle (Aura)"): ("Supported", "Enemy within 6\" suffers -2 Move and -1 OC."),
        ("DG", "Nurgle\u2019s Rot (Psychic)"): ("Supported", "End of Movement: select enemy within 12\"; -1 Toughness until next Movement."),
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
        ("DG", "Death\u2019s Heads"): (
            "Supported",
            "Post-shoot: select a hit enemy unit; friendly keyword units re-roll Wound rolls vs that unit until end of turn.",
        ),
        ("NEC", "Resurrection Orb"): (
            "Supported",
            "Once per battle, end of any phase: optional target selection supports both variants (nearby NECRONS INFANTRY/MOUNTED within 6\" and bearer-leading-unit only), activates Reanimation Protocols for D6 wounds, and enforces at most one resurrected unit per turn.",
        ),
        ("NEC", "Voice of the Triarch"): (
            "Supported",
            "Start of each battle round, select exactly one Triarch ability for The Silent King (Phaeron of the Stars, Phaeron of the Blades, or Relentless March); only the selected Triarch aura is active until the next battle round.",
        ),
        ("DG", "Blight Bombardment"): (
            "Supported",
            "Start of Shooting: select a visible enemy within 30\"; friendly DEATH GUARD ranged attacks vs that unit re-roll Hit rolls of 1, and BLAST attacks can re-roll Hit rolls.",
        ),
        ("DG", "Blistering Fusillade"): (
            "Supported",
            "Ranged attacks vs Afflicted targets gain +1 Strength and +1 AP when unit Starting Strength is 5+ or when led by a CHARACTER.",
        ),
        ("DG", "Death Approaches"): (
            "Supported",
            "Deep Strike placement supports split distances: more than 6\" from Afflicted enemy units and more than 9\" from other enemy units.",
        ),
        ("DG", "Eater Plague (Psychic)"): (
            "Supported",
            "Shooting phase optional target selection within 18\" and visible (with Lone Operative exclusion logic), then resolve mortal wounds via D6 table.",
        ),
        ("DG", "Horrifying Visage"): (
            "Supported",
            "After ending a Charge move, select one engaged enemy unit to take a Battle-shock test at -1.",
        ),
        ("DG", "Host of Plagues"): (
            "Supported",
            "End of Movement: roll for each enemy unit within 6\"; add +1 vs Afflicted units and on 3+ deal D3 mortal wounds.",
        ),
        ("DG", "Metalophagic Infection"): (
            "Supported",
            "After shooting, select a hit enemy MONSTER/VEHICLE; roll D6 (+1 if Afflicted) and on 5+ deal D3 mortal wounds.",
        ),
        ("DG", "Putrefying Stink"): (
            "Supported",
            "Enemy models cannot start or end an Advance move within 9\"; advance path validation enforces the denial.",
        ),
        ("DG", "Spore-laced Shock Waves"): (
            "Supported",
            "When selecting targets for Plagueburst mortar, roll for target and nearby enemy units; struck units suffer mortal wounds after attacks are resolved.",
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
        ("DG", "Diseased Cover"): (
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
        ("DG", "Virulent Blessing (Psychic)"): (
            "Supported",
            "Start of Fight: select a visible enemy within 24\"; PLAGUE LEGIONS attacks allocated to that unit gain +1 Damage until end of phase.",
        ),
        ("CD", "Altered Reality (Psychic)"): (
            "Supported",
            "Once per battle round, after a hit/wound/save roll for this model, change the result to a 6.",
        ),
        ("CSM", "Altered Reality (Psychic)"): (
            "Supported",
            "Once per battle round, after a hit/wound/save roll for this model, change the result to a 6.",
        ),
        ("CD", "Chaos Familiar"): (
            "Supported",
            "Once per battle, when an attack is allocated to the bearer, change the Damage characteristic to 0.",
        ),
        ("CSM", "Chaos Familiar"): (
            "Supported",
            "Once per battle, when an attack is allocated to the bearer, change the Damage characteristic to 0.",
        ),
        ("CD", "Harmonic Alignment"): (
            "Supported",
            "Command phase while leading: return D3 destroyed Bodyguard models.",
        ),
        ("CD", "Discordant Disruption (Aura)"): (
            "Supported",
            "Enemy PSYKER units within 12\": Psychic weapons gain [HAZARDOUS].",
        ),
        ("CD", "P’tarix’s Sorcerous Syphon (Aura)"): (
            "Supported",
            "Enemy units within 12\": Psychic attacks suffer -1 to wound.",
        ),
        ("CD", "Unholy Vigour"): (
            "Supported",
            "Once per battle, start of any phase: bearer gains a 3+ invulnerable save until end of phase.",
        ),
        ("CSM", "Cruel Hunter"): ("Supported", "Leading: pile-in/consolidate up to 6\"."),
        ("CSM", "Brutal Raider"): (
            "Supported",
            "Charge end: this model's melee weapons gain +1 Strength and +1 AP until end of turn.",
        ),
        ("CSM", "Chance for Glory"): (
            "Supported",
            "Once per battle, start of Fight phase: improve S/A/AP/D of the bearer's melee weapons by 1 until end of phase.",
        ),
        ("CSM", "Despoilers"): ("Supported", "After making a Dark Pact, unit re-rolls Hit rolls until end of phase."),
        ("CSM", "Raider's Due"): (
            "Supported",
            "Charge declarations can re-roll the Charge roll when one or more targets are within range of an objective marker.",
        ),
        ("CSM", "Lord of Badab (Aura)"): (
            "Supported",
            "Friendly HERETIC ASTARTES INFANTRY units within 6\" gain +1 Objective Control, excluding Battle-shocked and DAMNED units.",
        ),
        ("CSM", "Trophy Takers"): (
            "Supported",
            "First enemy unit destroyed by this unit grants +1 Objective Control to its models until end of battle while the unit is not Battle-shocked.",
        ),
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
        ("CSM", "Dark Ascension (Aura)"): (
            "Supported",
            "Friendly HERETIC ASTARTES units within 6\" gain both Dark Pacts weapon effects for that pact until end of phase.",
        ),
        ("CSM", "Dark Destiny"): (
            "Supported",
            "After passing a Dark Pacts Leadership test with a 7+, gain 1CP.",
        ),
        ("CSM", "Spirit Thief"): (
            "Supported",
            "Start of Shooting: select a visible enemy VEHICLE; friendly HERETIC ASTARTES attacks re-roll Wound rolls of 1 vs that unit until end of phase.",
        ),
        ("CSM", "Corrupt Machine Spirits"): (
            "Supported",
            "Start of Shooting: select a visible enemy VEHICLE within 12\"; roll D6 for mortal wounds (2-3=D3, 4-5=3, 6=D3+3).",
        ),
        ("CSM", "Daemonic Ordnance"): (
            "Supported",
            "When selected to shoot, optional activation grants [DEVASTATING WOUNDS] and [HAZARDOUS] to the model's ranged weapons until end of phase.",
        ),
        ("CSM", "Warp Rift Firepower"): (
            "Supported",
            "Once per battle in Shooting phase, optional activation grants [INDIRECT FIRE] to the unit's ranged weapons until end of phase.",
        ),
        ("CSM", "Surgeon Acolyte"): (
            "Supported",
            "Once per turn, when an attack is allocated to the unit and it contains FABIUS BILE, you can set that attack's Damage to 0.",
        ),
        ("CSM", "Swift Assault"): ("Supported", "Leading: unit ranged weapons gain Assault."),
        ("CSM", "Warp Strike"): ("Supported", "End of Fight: if destroyed an enemy unit and not engaged, enter Strategic Reserves."),
        ("ADM", "Dynamic Efficiency"): ("Partial", "Charge-after-Advance/Fall Back supported; Desperate Escape rerolls not implemented."),
        ("ADM", "Elevated Strider"): ("Partial", "Shoot-after-Fall-Back/Advance supported; Desperate Escape rerolls not implemented."),
        ("ADM", "Enginseer"): ("Partial", "Lone Operative applied without 3\" Vehicle proximity or leading restriction."),
        ("ADM", "Data-spike"): (
            "Supported",
            "Start of Fight phase: optional engaged enemy VEHICLE selection; on 4+ it suffers D6 mortal wounds and its melee weapon Weapon Skill is worsened by 1 until end of phase.",
        ),
        ("ADM", "Mechanicus Bodyguard"): ("Supported", "Conditional Lone Operative within 3\" of friendly ADEPTUS MECHANICUS units."),
        ("ADM", "Shroudpsalm (Aura)"): ("Partial", "Stealth applied to bearer only; aura not propagated."),
        ("AM", "Alchemyk Counteragents"): ("Supported", "Feel No Pain 6+ against mortal wounds."),
        ("AM", "Desert Riders"): ("Partial", "Shoot and charge after Falling Back; ignores Move/Advance/Charge modifiers not handled."),
        ("AM", "Deathstrike Missile"): (
            "Supported",
            "Shooting phase action support: optional Designate/Adjust/None flow places or moves a unique Deathstrike marker for the unit, with phase-use and ONE SHOT constraints enforced.",
        ),
        ("AM", "Enginseer"): ("Supported", "Conditional Lone Operative within 3\" of friendly ASTRA MILITARUM VEHICLE units."),
        ("AM", "Horsemasters"): ("Supported", "Shoot and charge after Falling Back."),
        ("AM", "LOYAL PROTECTOR"): (
            "Supported",
            "Declare Battle Formations: must join one COMMAND SQUAD if eligible, otherwise removed as destroyed; joined model counts as part of the unit, can embark with it, and uses 3 transport slots. Warlord and Enhancements restrictions from LOYAL PROTECTOR text variants are parsed.",
        ),
        ("AM", "Ogryn Bodyguard"): (
            "Supported",
            "While one or more OFFICER models are in the same attached unit as this model, OFFICER models in that unit gain Feel No Pain 4+.",
        ),
        ("AM", "Plasma Warhead"): (
            "Supported",
            "Marker-based firing is implemented: must remain stationary, cannot fire in a phase where Designate/Adjust was used, and resolves attacks against each unit within 6\" of the unit's Deathstrike marker without selecting a target unit.",
        ),
        ("GC", "Deathstrike Missile"): (
            "Supported",
            "Shooting phase action support: optional Designate/Adjust/None flow places or moves a unique Deathstrike marker for the unit, with phase-use and ONE SHOT constraints enforced.",
        ),
        ("GC", "Plasma Warhead"): (
            "Supported",
            "Marker-based firing is implemented: must remain stationary, cannot fire in a phase where Designate/Adjust was used, and resolves attacks against each unit within 6\" of the unit's Deathstrike marker without selecting a target unit.",
        ),
        ("AM", "Slabshield"): (
            "Supported",
            "Bearer wounds characteristic set-value clauses are parsed (e.g., Wounds characteristic becomes 4 or 7 based on the ability text).",
        ),
        ("AM", "Malign Wardings(Psychic)"): ("Supported", "Leading: Feel No Pain 4+ against Psychic attacks."),
        ("GK", "Apothecary's Narthecium"): ("Supported", "Command phase: return 1 destroyed non-CHARACTER model to the bearer's unit."),
        ("GK", "Attuned Onslaught (Psychic)"): ("Supported", "After charging, PALADIN SQUAD melee weapons gain +1 Damage until end of turn."),
        ("GK", "Blessing of the Omnissiah"): ("Supported", "Command phase: select friendly VEHICLE within 3\" to regain D3 wounds and gain +1 to hit until next Command phase."),
        ("GK", "Champion of the Order of Purifiers (Psychic)"): ("Supported", "Leading: Purifying Flame weapons in the unit gain +1 Attack."),
        ("GK", "Eye of Judgement (Psychic)"): ("Supported", "Model attacks can re-roll the Wound roll."),
        ("GK", "Fire Focus"): ("Supported", "Post-shoot: mark a hit enemy; disembarked friendly models from this TRANSPORT gain +1 AP vs that target until end of turn."),
        ("GK", "Force Edge (Psychic)"): ("Supported", "Melee attacks gain +1 AP vs non-MONSTER/non-VEHICLE targets."),
        ("GK", "Guardians of the Machine"): ("Supported", "Heroic Intervention can target this unit for 0CP (with repeat-use bypass) when trigger conditions are met."),
        ("GK", "Guidance of the Ancients (Psychic)"): ("Supported", "Post-shoot: mark a hit enemy; friendly GREY KNIGHTS models gain +1 to hit vs that target until end of phase."),
        ("GK", "Hammer Aflame (Psychic)"): ("Supported", "Fight selection: optional enemy within Engagement Range suffers mortal wounds on 2-3/4-5/6 table."),
        ("GK", "Inspiring Exemplar"): ("Supported", "Fight-phase CHARACTER model kills grant 1CP and +1 Attack to Nemesis force weapon until end of battle."),
        ("GK", "Indomitable Spirit (Psychic)"): ("Supported", "Shoot and charge after Advance/Fall Back."),
        ("GK", "Might of Titan (Psychic)"): ("Supported", "Once per battle at start of Fight phase: optional +3 Attacks and +3 Strength for melee weapons until end of phase."),
        ("GK", "Personal Teleporters"): ("Supported", "Post-shoot: optional Normal move up to 6\" when not engaged; unit cannot charge this turn."),
        ("GK", "Retinue"): ("Supported", "While led by a BROTHERHOOD TECHMARINE, unit gains Deep Strike and Teleport Assault grant is recognized by Gate of Infinity eligibility."),
        ("GK", "Righteous Persecution"): ("Supported", "Post-shoot: select hit non-MONSTER/non-VEHICLE enemy; target is pinned (Move -2, Charge -2)."),
        ("GK", "Sanctic Hood"): ("Supported", "Leading: Feel No Pain 4+ against Psychic attacks."),
        ("GK", "Sanctity of Purpose"): ("Supported", "Unit attacks re-roll Wound rolls of 1; attacks vs targets within objective range can re-roll the Wound roll."),
        ("GK", "Surge of Wrath (Psychic)"): ("Supported", "Melee attacks vs MONSTER/VEHICLE can re-roll Hit, Wound, and Damage rolls."),
        ("GK", "Techmarine"): ("Supported", "Conditional Lone Operative within 3\" of friendly GREY KNIGHTS VEHICLE units."),
        ("GK", "Truesilver Aegis (Aura)"): ("Supported", "Friendly GREY KNIGHTS units wholly within 6\" gain Feel No Pain 6+ against mortal wounds."),
        ("GK", "Untouchable Purity"): ("Supported", "Leading only: bearer’s attached unit gains Feel No Pain 4+ against mortal wounds."),
        ("GK", "Haloed in Soulfire (Psychic)"): (
            "Supported",
            "Leading: attached unit can only be targeted by ranged attacks within 18\".",
        ),
        ("AOI", "Abomination"): ("Supported", "Feel No Pain 2+ against Psychic attacks."),
        ("AOI", "Backroom Deals"): ("Partial", "Infiltrators applied without formation selection/leading restriction."),
        ("AOI", "Frenzon"): ("Supported", "Shoot and charge after Advancing."),
        ("AOI", "Psychic Hood"): ("Supported", "Feel No Pain 4+ against Psychic attacks."),
        ("AOI", "NAVY BODYGUARD"): (
            "Supported",
            "Assigned Agents: in non-AOI armies, each VOIDFARERS CHARACTER unit allows one VOIDSMEN-AT-ARMS unit to ignore RETINUE caps.",
        ),
        ("AOI", "INQUISITORIAL HENCHMEN"): (
            "Supported",
            "Assigned Agents: in non-AOI armies, each INQUISITOR unit allows one INQUISITORIAL AGENTS unit to ignore RETINUE caps.",
        ),
        ("AOI", "SHADOW ASSIGNMENT"): (
            "Supported",
            "During Declare Battle Formations, eligible OFFICIO ASSASSINORUM models can be replaced via SHADOW_ASSIGNMENT decisions with points cap and duplicate-assassin validation.",
        ),
        ("AOI", "Rites of Teleportation"): ("Partial", "Deep Strike granted without Inquisitor attachment restriction."),
        ("AOI", "Unsubtle Crusader"): ("Partial", "Scouts 6\" applied without formation selection/target-unit restriction."),
        ("AE", "ASPECT TRAINING"): (
            "Supported",
            "Leading: grants Fights First when attached to Howling Banshees; grants Infiltrators/Scouts 7\"/Stealth when attached to Striking Scorpions.",
        ),
        ("AE", "Aspect Shrine Token"): (
            "Supported",
            "Per-roll prompt lets non-CHARACTER models change a hit or wound roll to an unmodified 6, consuming a token; tokens tracked from wargear options with per-activation prompt suppression, and attached CHARACTERS do not retain tokens when the Aspect Warriors bodyguard is destroyed.",
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
        ("DRU", "Choreographer of War"): (
            "Supported",
            "Leading: pile-in/consolidate up to 6\" and must end as close as possible to the closest enemy unit.",
        ),
        ("AE", "Cegorach's Favour"): (
            "Supported",
            "Once per turn: first failed saving throw for the bearer's unit sets that attack's Damage to 0.",
        ),
        ("DRU", "Cegorach's Favour"): (
            "Supported",
            "Once per turn: first failed saving throw for the bearer's unit sets that attack's Damage to 0.",
        ),
        ("AE", "Channeller Stones"): (
            "Supported",
            "Once per turn: first failed saving throw for the bearer's unit sets that attack's Damage to 0.",
        ),
        ("DRU", "Channeller Stones"): (
            "Supported",
            "Once per turn: first failed saving throw for the bearer's unit sets that attack's Damage to 0.",
        ),
        ("AE", "Dance of Death"): (
            "Supported",
            "Leading: at the start of the Fight phase choose Hero's Prowess (re-roll hit 1s), Villain's Doom (+1 to wound), or Trickster's Grace (-1 to hit vs the unit).",
        ),
        ("DRU", "Dance of Death"): (
            "Supported",
            "Leading: at the start of the Fight phase choose Hero's Prowess (re-roll hit 1s), Villain's Doom (+1 to wound), or Trickster's Grace (-1 to hit vs the unit).",
        ),
        ("DRU", "Airborne Evasion"): (
            "Supported",
            "After shooting: if not within Engagement Range, unit can make a Normal move up to 6\" and cannot charge this turn.",
        ),
        ("AE", "Cruel Amusement"): (
            "Supported",
            "Selected to shoot: choose Ignores Cover, Precision, or Sustained Hits 3 for the shrieker cannon until end of phase.",
        ),
        ("DRU", "Cruel Amusement"): (
            "Supported",
            "Selected to shoot: choose Ignores Cover, Precision, or Sustained Hits 3 for the shrieker cannon until end of phase.",
        ),
        ("DRU", "Murderous Crossfire"): (
            "Supported",
            "After shooting: select a hit enemy unit; friendly DRUKHARI ranged attacks against that target improve AP by 1 until end of phase (once per turn per target).",
        ),
        ("DRU", "Mind Like a Steel Trap (Aura)"): (
            "Supported",
            "Opponent Stratagem targeting: if target is within 12\", increase CP cost by 1.",
        ),
        ("DRU", "Kabalite Icon"): (
            "Supported",
            "Bearer's unit gains +1 Objective Control (Battle-shocked units already have OC 0 by core rules).",
        ),
        ("DRU", "Phantasm Grenade Launcher"): (
            "Supported",
            "Bearer's unit gains Smoke and Grenades keywords when specified by the datasheet rule text.",
        ),
        ("DRU", "Stimm-needler"): (
            "Supported",
            "Once per turn: first failed saving throw for the bearer's unit sets that attack's Damage to 0.",
        ),
        ("DRU", "Pain Adept"): (
            "Supported",
            "Command phase: if one or more models with this ability are on the battlefield, roll one D6 and gain 1 Pain token on 4+.",
        ),
        ("DRU", "Pain Engine (Aura)"): (
            "Supported",
            "Each time 1 Pain token is spent to Empower a friendly unit within 9\", roll one D6 (add 1 if one or more models in this unit are not equipped with a spirit vortex); on 5+, gain 1 Pain token.",
        ),
        ("DRU", "Torture Device"): (
            "Supported",
            "Each time this unit destroys an enemy unit, you gain 1 additional Pain token.",
        ),
        ("DRU", "Fear Incarnate (Aura)"): (
            "Supported",
            "Opponent Command phase Battle-shock step: enemy units below Starting Strength within range must test; PSYKER units take the specified penalty.",
        ),
        ("DRU", "Tormentors"): (
            "Supported",
            "Start of Fight phase: enemy units within Engagement Range of units with this ability must take Battle-shock tests; melee attacks gain +1 to hit vs Battle-shocked units.",
        ),
        ("DRU", "Torturer's Craft"): (
            "Supported",
            "Shooting/Fight phase after this unit has shot or fought: select one hit enemy unit (excluding VEHICLES); it must take a Battle-shock test.",
        ),
        ("DRU", "Incubi Shrine Token"): (
            "Supported",
            "Per-roll token prompt lets the unit spend shrine tokens to change one Hit or Wound roll to an unmodified 6, consuming a token each time.",
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
        ("DRU", "Treacherous Illusion (Psychic)"): (
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
        ("DRU", "Death is Not Enough"): (
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
        ("DRU", "Piratical Raiders"): (
            "Supported",
            "Start of battle: select an enemy unit; this unit's weapons gain Lethal Hits and Precision vs that unit.",
        ),
        ("AE", "Piratical Hero"): (
            "Supported",
            "Leading: each attack made by models in that unit gains Sustained Hits 1 and +1 to hit.",
        ),
        ("AE", "Prince of Corsairs"): (
            "Supported",
            "After deployment, if this unit is on the battlefield (or embarked in a transport on the battlefield), redeploy up to three friendly AELDARI units; selected units may be placed into Strategic Reserves regardless of limits.",
        ),
        ("AE", "Raid and Run"): (
            "Supported",
            "End of Fight phase: if this unit was eligible to fight this phase, it can make a D3+3\" move (Normal move if not engaged; Fall Back move if engaged).",
        ),
        ("AE", "Hallucinogen Grenades"): (
            "Supported",
            "Start of opponent Shooting phase: optional selection of a visible friendly AELDARI INFANTRY unit within 36\"; selected unit gains Stealth until end of phase.",
        ),
        ("AE", "Fury of the Void (Psychic)"): (
            "Supported",
            "After shooting with Dread of the Deep Void hits: select a hit enemy unit to become riven; until end of turn friendly AELDARI attacks targeting that unit gain +1 Strength.",
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
        ("CSM", "Blood Surge"): ("Supported", "Opponent Shooting phase: optional D6+2\" move toward closest non-AIRCRAFT enemy; blocked if Battle-shocked/engaged; once per phase."),
        ("CSM", "Guns Blazing"): (
            "Supported",
            "Once per turn in opponent Shooting phase: when an enemy unit shoots a friendly HERETIC ASTARTES unit within 3\", this model can shoot that enemy unit out of phase.",
        ),
        ("CSM", "The Warmaster"): (
            "Supported",
            "Command phase choice: select one Warmaster ability until your next Command phase; only the selected Paragon/Mark/Lord ability is active.",
        ),
        ("CSM", "Voice Eater"): (
            "Supported",
            "Enemy non-MONSTER/VEHICLE units within Engagement Range cannot be targeted by Stratagems.",
        ),
        ("CSM", "Daemonforge"): (
            "Supported",
            "Once per Fight phase, one unit with this ability can use Counter-offensive for 0CP even if already used this phase.",
        ),
        ("CSM", "Chirurgeon"): (
            "Supported",
            "First time this unit's FABIUS BILE model is destroyed: end-of-phase 2+ return with full wounds; if attached when destroyed, return attached to that unit.",
        ),
        ("CSM", "Enrage Machine Spirits"): (
            "Supported",
            "End of your Movement phase: optional enemy VEHICLE within range takes a Battle-shock test.",
        ),
        ("CSM", "Flying Horror"): (
            "Supported",
            "After this model ends a Normal/Advance move, select a moved-over enemy unit to take a Battle-shock test.",
        ),
        ("CSM", "Enhanced Warriors"): (
            "Supported",
            "If attached at battle start, bodyguard models gain +1 Toughness and +1 Strength on melee weapons.",
        ),
        ("CSM", "Chosen Marauders"): ("Supported", "Shoot and charge after Advance/Fall Back."),
        ("CSM", "Hovering Death"): ("Supported", "Shoot and charge after Falling Back."),
        ("CSM", "Daemonic Allegiance"): (
            "Supported",
            "Mandatory Khorne/Tzeentch/Nurgle/Slaanesh selection is parsed and applied, including keyword and characteristic modifiers.",
        ),
        ("CSM", "Khorne"): ("Supported", "Daemonic Allegiance option: hellforged weapon Strength +2."),
        ("CSM", "Nurgle"): ("Supported", "Daemonic Allegiance option: Toughness +1."),
        ("CSM", "Slaanesh"): ("Supported", "Daemonic Allegiance option: Move +2\"."),
        ("CSM", "Tzeentch"): ("Supported", "Daemonic Allegiance option: infernal cannon Attacks +3."),
        ("CSM", "Scuttling Walker"): (
            "Supported",
            "Normal/Advance movement can pass over friendly MONSTER/VEHICLE models and terrain up to 4\" high.",
        ),
        ("CSM", "Bringers of Change"): (
            "Supported",
            "Ranged attacks re-roll Wound rolls of 1; full Wound re-rolls vs targets within objective range of an objective marker you do not control.",
        ),
        ("CSM", "Reorder Reality"): (
            "Supported",
            "When an enemy unit targets this unit in Shooting phase and is within 18\", that enemy unit's ranged attacks become [HAZARDOUS] and suffer -1 to hit this phase (vs marked targets).",
        ),
        ("CSM", "Siege Crawler"): (
            "Supported",
            "Ignores modifiers to Move characteristic and Advance/Charge roll modifiers.",
        ),
        ("CSM", "Siege Shield"): (
            "Supported",
            "Demolisher Cannon attack exception implemented for Big Guns Never Tire/Blast own-engagement targeting interactions.",
        ),
        ("CSM", "Soul Eater"): (
            "Supported",
            "End of Fight phase: after destroying an enemy unit this phase, gains cumulative +1 Attacks bonus for its weapons.",
        ),
        ("CSM", "Plough Through the Enemy"): (
            "Supported",
            "End of Fight phase: after destroying an enemy unit this phase, enemy units within 6\" take Battle-shock tests.",
        ),
        ("CSM", "Herald of the Apocalypse (Aura)"): (
            "Supported",
            "Opponent Command phase: below Starting Strength enemy units within 6\" take Battle-shock tests.",
        ),
        ("CSM", "Herald of the Apocalypse"): (
            "Supported",
            "Opponent Command phase: below Starting Strength enemy units within 6\" take Battle-shock tests.",
        ),
        ("CSM", "Master of Mechanisms"): (
            "Supported",
            "Command phase: optional CHOOSE_QUARRY target selection (with None), D3 heal to a friendly VEHICLE within 3\", and +1 to hit until next Command phase.",
        ),
        ("CSM", "Red Corsairs"): (
            "Supported",
            "Post-deployment redeploy support, including Strategic Reserves placement regardless of current reserves count.",
        ),
        ("CSM", "MASTERS OF THE MAELSTROM"): (
            "Supported",
            "Declare Battle Formations: this unit can join CHOSEN, LEGIONARIES, or RED CORSAIRS RAIDERS that are not already Attached units; after joining, only Huron Blackheart can attach as Leader to that unit.",
        ),
        ("CSM", "Annihilator"): (
            "Supported",
            "Ranged attacks against MONSTER/VEHICLE apply model-level Damage re-roll support.",
        ),
        ("CSM", "Destructor"): (
            "Supported",
            "Model-level ranged AP improvement vs enemy INFANTRY targets.",
        ),
        ("CSM", "Outmanoeuvre"): (
            "Supported",
            "On turns in which the unit charged, melee attacks gain +1 Strength.",
        ),
        ("CSM", "Icon of Khorne"): (
            "Supported",
            "Enemy units destroyed by the bearer unit grant Bloodshed points consumed by Blessings of Khorne rolls.",
        ),
        ("CSM", "Ascended Daemon"): (
            "Supported",
            "Selected to shoot/fight grants one Hit re-roll and one Wound re-roll while resolving attacks.",
        ),
        ("CSM", "Head Taker"): (
            "Supported",
            "Charge-end enemy selection: roll D6 per model in the unit; each 4+ inflicts 1 mortal wound.",
        ),
        ("CSM", "Dark Blessing (Aura)"): (
            "Supported",
            "Friendly HERETIC ASTARTES INFANTRY within 6\" gain Benefit of Cover vs ranged attacks.",
        ),
        ("CSM", "Mark of Chaos Ascendant (Aura)"): (
            "Supported",
            "Warmaster-selected aura: friendly HERETIC ASTARTES INFANTRY/MOUNTED units within 6\" (excluding DAMNED) have a 4+ invulnerable save.",
        ),
        ("CSM", "Paragon of Hatred (Aura)"): (
            "Supported",
            "Friendly HERETIC ASTARTES (excluding DAMNED) within 6\" gain full Hit re-roll support.",
        ),
        ("CSM", "Lord of the Traitor Legions (Aura)"): (
            "Supported",
            "Friendly HERETIC ASTARTES (excluding DAMNED) within 6\" can re-roll Leadership and Battle-shock tests.",
        ),
        ("CSM", "Icon of Despair (Aura)"): (
            "Supported",
            "Enemy units within 6\" of the bearer have Leadership worsened by 1.",
        ),
        ("CSM", "Malevolent Locus (Aura)"): (
            "Supported",
            "Friendly HERETIC ASTARTES models within 9\" gain Leadership improvement.",
        ),
        ("CSM", "Mind-breaking Mutations (Aura)"): (
            "Supported",
            "Enemy non-VEHICLE units within 3\" suffer -1 Objective Control.",
        ),
        ("CSM", "Hamadrya's Knowledge (Psychic)"): (
            "Supported",
            "Reactive move trigger: once per battle round, when an enemy ends a Normal/Advance/Fall Back move within 9\" and this unit is not engaged, it can make a Normal move up to D3+3\".",
        ),
        ("CSM", "Malign Cover"): (
            "Supported",
            "Fortification cover support: ranged attacks allocated to models not fully visible because of this FORTIFICATION grant Benefit of Cover.",
        ),
        ("CSM", "Infused with the Blessings of Nurgle"): (
            "Supported",
            "Post-shoot selection: choose a hit enemy unit; it is marked Afflicted until the start of your next turn.",
        ),
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
        ("DG", "Blinding Spray"): ("Supported", "Fight phase CHOOSE_QUARRY selection (with None) grants Fights First until phase end; once per model per battle."),
        ("DG", "Gift of Poxes"): ("Supported", "While bearer is on the battlefield, Nurgle's Gift contagion range increases by 3\"."),
        ("DG", "Miasma of Pestilence (Aura)"): ("Supported", "Friendly DEATH GUARD units within 6\" gain Benefit of Cover against ranged attacks."),
        ("DG", "Pestilent Fallout (Psychic)"): ("Supported", "Post-shoot: select an enemy INFANTRY unit hit by Plague Wind; it is enfeebled (-2\" Move) through opponent turn."),
        ("DG", "Sevenfold Chant"): ("Supported", "Command phase 2D6 roll; on 7+ gain 1CP."),
        ("DG", "Sickening Vitality"): ("Supported", "While leading: attached unit has Move +1\" and can re-roll Advance and Charge rolls."),
        ("DG", "Silent Bodyguard"): ("Supported", "While a CHARACTER leads the unit, that CHARACTER gains Feel No Pain 4+."),
        ("DG", "Tocsin of Misery (Aura)"): ("Supported", "Opponent Command phase: below Starting Strength enemies within 9\" test Battle-shock; PSYKER targets take the test at -1."),
        ("DG", "Unholy Resilience"): ("Supported", "First destruction each battle round can return at end of phase on 2+ with remaining wounds, once per battle."),
        ("DG", "Shroud of Disease"): ("Supported", "Leading: attached unit can only be targeted by ranged attacks within 18\"."),
        ("DG", "Boon of Death"): (
            "Supported",
            "Opponent Fight phase reaction: once per turn, choose a friendly DEATH GUARD unit within 6\" that was selected as a melee target; that unit gains melee fight-on-death on 2+ until end of phase.",
        ),
        ("DG", "Diseased Influence"): (
            "Supported",
            "Opponent Movement phase reaction: once per turn after an enemy ends a Normal/Advance/Fall Back move within 9\", choose a friendly DEATH GUARD unit within 6\" (not engaged) to make a reactive Normal move up to 5\".",
        ),
        ("DG", "Explosive Blight"): (
            "Supported",
            "After this model destroys an enemy unit in Shooting, roll D6 (+1 if destroyed unit is Afflicted); on 5+, other enemy units within 6\" become Afflicted until your next turn.",
        ),
        ("DG", "Extraction of Fresh Disease"): (
            "Supported",
            "Once per battle, when this model's melee weapon destroys an enemy unit, that model gains +6 Objective Control for the rest of the battle.",
        ),
        ("DG", "Icon of Despair (Aura)"): (
            "Supported",
            "Enemy units within 6\" of the bearer have Leadership worsened by 1.",
        ),
        ("DG", "Inflamed Infections"): (
            "Supported",
            "Start of Fight phase: optional engaged enemy selection (with None) for the model; that model scores critical hits on 5+ (or 4+ while target is Below Half-strength) against the chosen unit until phase end.",
        ),
        ("DG", "Inflamed Reprisal"): (
            "Supported",
            "Opponent Shooting phase reaction: once per turn, choose a friendly DEATH GUARD unit within 6\" and not Battle-shocked that was targeted by the attacker; after attacks resolve, it can shoot that attacker out of phase.",
        ),
        ("DG", "Lethal Ichor"): (
            "Supported",
            "Fight phase: each time a melee attack is allocated to this unit, track allocations (max 6) by attacker; after attacker resolves, roll D6 per allocation and deal 1 mortal wound per 4+ to the attacker.",
        ),
        ("DG", "Curse of the Walking Pox"): (
            "Supported",
            "Track enemy model kills by POXWALKER attacks (and Eater Plague where applicable) and offer an end-of-sequence optional return count selection to return destroyed Poxwalker Bodyguard models.",
        ),
        ("DG", "Lord of the Death Guard"): (
            "Supported",
            "Mortarion once-per-turn gate for Boon of Death, Inflamed Reprisal, and Diseased Influence with deterministic turn ownership tracking.",
        ),
        ("DG", "DEPLOYMENT"): (
            "Supported",
            "Miasmic Malignifier deployment is represented by standard fortification setup in the engine; the two-piece terrain representation is abstracted to a single fortification unit for gameplay effects.",
        ),
        ("DRU", "ARCHON'S RETINUE"): (
            "Supported",
            "If attached during Declare Battle Formations, the attached Leader gains Scouts 7\"; the bodyguard unit does not gain Scouts from this ability.",
        ),
        ("DRU", "Blur of Blades"): ("Supported", "Leading: unit gains Fights First."),
        ("DRU", "Blur of Movement"): ("Supported", "Charge-after-Advance eligibility."),
        ("DRU", "Aethersails"): ("Supported", "Advance: fixed +6\" Move instead of rolling."),
        ("DRU", "Archon's Will"): (
            "Supported",
            "Start of first battle round objective selection is decision-routed; while in range of the selected objective and not Battle-shocked, the unit has a 5+ invulnerable save and OC 3.",
        ),
        ("DRU", "Disparate Paths"): (
            "Supported",
            "Mustering restrictions validated: allows DRUKHARI armies to include HARLEQUINS units while rejecting non-permitted faction-keyword mixes; HARLEQUINS/Ynnari Army Faction selection is disallowed by validation.",
        ),
        ("DRU", "Precognisant"): (
            "Supported",
            "After deployment redeploy supports selecting up to three DRUKHARI units with optional Strategic Reserves placement regardless of normal reserve limits.",
        ),
        ("DRU", "Vanguard of the Dark City"): (
            "Supported",
            "Start of Command phase mode selection is decision-routed (Masters of the Shadowed Sky, Speed of the Kill, or Visions of Butchery) and persisted until the next Command phase.",
        ),
        ("DRU", "Masters of the Shadowed Sky"): (
            "Supported",
            "Sticky objective transport clause applies only while this Vanguard mode is selected and one or more Kabalite Warriors units are embarked.",
        ),
        ("DRU", "Speed of the Kill"): (
            "Supported",
            "While this Vanguard mode is selected, WYCHES disembarking from this model use a 6\" disembark placement distance (excluding Emergency Disembarkation flow).",
        ),
        ("DRU", "Visions of Butchery"): (
            "Supported",
            "While this Vanguard mode is selected, bladevanes/chainsnares gain +1 Attacks per embarked WRACKS model.",
        ),
        ("DRU", "Void Mine"): (
            "Supported",
            "Once per battle after a Normal move: optional moved-over enemy model selection (with None), then roll radius and resolve per-enemy-unit 4+ to inflict D6 mortal wounds within that radius.",
        ),
        ("DRU", "Eviscerating Fly-by"): (
            "Supported",
            "Normal/Advance move over: select a moved-over enemy; roll D6 per model (supports FLY bonus and exclusions).",
        ),
        ("DRU", "Cluster Caltrops"): ("Supported", "Re-roll move-over mortal wound dice (one per model with Cluster Caltrops)."),
        ("DRU", "Fog of Dreams (Psychic)"): ("Supported", "Leading: attached unit can only be targeted by ranged attacks within 18\"."),
        ("DRU", "Polychromatic Camouflage"): ("Supported", "Ranged attacks can only target this unit within 18\"."),
        ("DRU", "Shade Weavers"): ("Supported", "Ranged attacks can only target this unit within 18\"."),
        ("GC", "Cult Icon"): (
            "Supported",
            "Command phase: return destroyed non-CHARACTER models to the bearer's unit; supports both variants (D3 or 3, with controlled-objective swap to 3 or D3+3).",
        ),
        ("GC", "Sudden Assault"): ("Supported", "Leading: unit gains Fights First."),
        ("GC", "Swift and Deadly"): ("Supported", "Charge-after-Advance eligibility."),
        ("LOV", "Brōkhyr Guild Support"): ("Supported", "Conditional Lone Operative within 3\" of friendly LEAGUES OF VOTANN VEHICLE or IRONKIN STEELJACKS units; disabled while attached."),
        ("LOV", "Breaching Fire"): ("Supported", "After shooting: select a hit enemy unit; it cannot gain Benefit of Cover until the start of your next Shooting phase."),
        ("LOV", "Cyberstimms"): ("Supported", "Melee fight-on-death after attacker resolves; roll gets +1 while your army has Fortify Takeover."),
        ("LOV", "Science Guild Support"): ("Supported", "Conditional Lone Operative within 3\" of other friendly LEAGUES OF VOTANN INFANTRY units, excluding units with Lone Operative."),
        ("LOV", "Ancestral Fortune"): ("Supported", "Once per turn, spend 1 YP to change one Hit/Wound/Save roll for the model to an unmodified 6 (decision-routed and YP-tracked)."),
        ("LOV", "Computational Mastermind"): ("Supported", "End of Command phase, before mode update: for each controlled objective with a model in range, choose gain 1 YP, spend 1 YP, or none."),
        ("LOV", "Decisive Destruction"): ("Supported", "Ranged attacks vs the closest eligible target re-roll Hit rolls of 1."),
        ("LOV", "Destabilising Quakes"): ("Supported", "Post-shoot selection: hit enemy unit takes a Battle-shock test at -1, including weapon-clause variants."),
        ("LOV", "Forgewrought Expertise"): ("Supported", "End of Movement phase selection (with None): repair friendly VEHICLE/EXOFRAME/IRONKIN STEELJACKS once per turn; heal D3 or flat 3 with Ironkin Assistant."),
        ("LOV", "Geomantic Hunters"): ("Supported", "Up to twice per battle in Shooting phase: optional activation grants Breacher Ordnance wound re-roll support for that phase."),
        ("LOV", "Mass Driver Accelerators"): ("Supported", "Charge end: select an engaged enemy and roll D6 (2-5: D3 mortal wounds; 6: D3+3 mortal wounds)."),
        ("LOV", "Multiwave Comms Array"): ("Supported", "When targeted by a Stratagem, roll D6 and gain 1 CP on 5+ (CP gain guardrail respected)."),
        ("LOV", "Opportunistic Manoeuvre"): ("Supported", "After shooting: optional Normal move up to D6\"; if used, unit cannot declare a charge that turn."),
        ("LOV", "Outflanking Mag-riders"): ("Supported", "End of opponent turn: if wholly within 9\" of a battlefield edge and not in Engagement Range, the unit may enter Strategic Reserves."),
        ("LOV", "Preymark Crest"): ("Supported", "Attacks targeting units within objective range gain [PRECISION] on a Critical Wound."),
        ("LOV", "Purge Response"): ("Supported", "Fire Overwatch for this unit hits on 5+; while your army has Fortify Takeover, it hits on 4+ instead."),
        ("LOV", "Resource Transmutation"): ("Supported", "Once per turn in Shooting phase: optional 1 YP spend enables Sustained Hits 1 for one model and post-shoot gain up to 2 YP decision on destroyed enemy."),
        ("LOV", "Scanner Uplinks"): ("Supported", "Post-shoot selection: hit enemy non-MONSTER/VEHICLE unit is suppressed until start of your next turn (-1 to hit)."),
        ("LOV", "Seized Opportunity"): ("Supported", "Once per phase when an enemy unit is destroyed by this unit: optional gain 1 YP confirmation."),
        ("LOV", "Grimnyr's Regard"): ("Supported", "Once per battle, start of any phase: clear Battle-shock on a friendly LEAGUES OF VOTANN unit within 12\" of the GRIMNYR model."),
        ("LOV", "Luck Has. Need Keeps. Toil Earns"): ("Supported", "Command phase sticky objective application (remains controlled until opponent has greater Level of Control at phase end)."),
        ("LOV", "Predictive Guidance"): ("Supported", "Once per battle round, this unit can be targeted with Fire Overwatch or Heroic Intervention for 0CP."),
        ("LOV", "Rollbar Searchlight"): ("Supported", "Ranged attacks by the bearer's unit can ignore any or all Hit roll modifiers."),
        ("LOV", "Subterranean Explosives"): ("Supported", "After shooting with a mole grenade launcher: select a hit enemy non-MONSTER/VEHICLE unit; it cannot be targeted by Fire Overwatch until your next Shooting phase."),
        ("LOV", "Teleport Crest"): ("Supported", "Models in the bearer's unit gain Deep Strike; leading-gated variants require the bearer to be leading."),
        ("LOV", "Unhinged Vengeance"): ("Supported", "Opponent Shooting phase reaction: if model lost wounds after enemy shooting, optional D6+2 reactive move toward closest non-AIRCRAFT enemy (can end in Engagement Range), once per phase."),
        ("NEC", "Adaptive Strategy"): ("Supported", "Shoot and charge after Falling Back."),
        ("NEC", "CRYPTEK RETINUE"): (
            "Supported",
            "Declare Battle Formations: this unit can join one bodyguard led by a CRYPTEK INFANTRY Leader; joined-support attachment updates attached-unit membership and Starting Strength aggregation.",
        ),
        ("NEC", "CANOPTEK RETINUE"): (
            "Supported",
            "Declare Battle Formations: this unit can join one bodyguard led by a CRYPTEK Leader; joined-support attachment updates attached-unit membership and Starting Strength aggregation.",
        ),
        ("NEC", "Ghostwalk Mantle"): ("Supported", "Leading: unit gains Fights First."),
        ("NEC", "Illuminor"): ("Supported", "Conditional Lone Operative within 3\" of friendly NECRONS units."),
        ("NEC", "Protective Disciples"): ("Supported", "Conditional Lone Operative within 3\" of friendly DESTROYER CULT units."),
        ("NEC", "VANGUARD PROTOCOLS"): (
            "Supported",
            "If attached to a CANOPTEK MACROCYTES unit during Declare Battle Formations, the model gains Scouts 8\"; otherwise no Scouts bonus.",
        ),
        ("AM", "DEPLOYMENT"): (
            "Supported",
            "Aegis Defence Line deployment enforces section composition limits and connectivity, including the broken-shield 1/2\" middle-pair exception, while treating all sections as one model.",
        ),
        ("GC", "DEPLOYMENT"): (
            "Supported",
            "Aegis Defence Line deployment enforces section composition limits and connectivity, including the broken-shield 1/2\" middle-pair exception, while treating all sections as one model.",
        ),
        ("NEC", "DEPLOYMENT"): (
            "Supported",
            "Convergence Of Dominion setup uses a 12\" model-to-model chain (instead of unit coherency) and then splits into single-model units so each Starstele is treated as a separate unit for the rest of the battle.",
        ),
        ("NEC", "TRIARCHAL MENHIRS"): (
            "Supported",
            "When this unit's Szarekh model is destroyed, all remaining TRIARCHAL MENHIR models in the unit are also destroyed.",
        ),
        ("NEC", "Relentless Combatants"): ("Supported", "Re-roll Charge rolls. Charge-after-Fall-Back eligibility."),
        ("NEC", "Shadowloom"): ("Supported", "Stealth."),
        ("NEC", "Powers of the C'tan"): (
            "Supported",
            "When selected to shoot, C'tan Power weapon declarations are capped to two distinct weapons (one while in the damaged bracket).",
        ),
        ("NEC", "Fabricator Claw Array (Aura)"): ("Supported", "Aura: friendly NECRONS VEHICLE units within 6\" gain Feel No Pain 6+."),
        ("NEC", "Gloom Prism (Aura)"): ("Supported", "Aura: friendly NECRONS units within 6\" gain Feel No Pain 5+ against mortal wounds and Psychic Attacks."),
        ("NEC", "Nullstone Field Generator (Aura)"): ("Supported", "Aura: friendly NECRONS units within 6\" gain Feel No Pain 5+ against mortal wounds and Psychic Attacks."),
        ("NEC", "Reanimation Nodes (Aura)"): ("Supported", "Aura: friendly NECRONS INFANTRY units within 6\" gain Feel No Pain 6+."),
        ("NEC", "Relentless March (Aura)"): ("Supported", "Aura: friendly NECRONS units within 6\" of Szarekh gain +2\" Move."),
        ("NEC", "The Silent King"): ("Supported", "Aura: friendly NECRONS units within 6\" of Szarekh improve Leadership by 1."),
        ("NEC", "Phaeron of the Stars (Aura)"): ("Supported", "Aura: friendly NECRONS units within 6\" of Szarekh re-roll Hit rolls of 1 and Wound rolls of 1."),
        ("NEC", "Phaeron of the Blades (Aura)"): ("Supported", "Aura: friendly NECRONS units within 6\" of Szarekh can re-roll Charge rolls and gain +1 Strength on melee attacks."),
        ("ORK", "Full Throttle"): ("Supported", "Charge-after-Advance and charge-after-Fall-Back eligibility."),
        ("ORK", "Mekboy"): ("Supported", "Conditional Lone Operative within 3\" of friendly ORKS VEHICLE units."),
        ("ORK", "BODYGUARD"): (
            "Supported",
            "Boyz BODYGUARD enforces two attached Leaders only at Starting Strength 20 and requires one attached Leader to have the WARBOSS keyword when two Leaders are attached.",
        ),
        ("ORK", "PATROL SQUAD"): (
            "Supported",
            "Declare Battle Formations: optional split into two 5-model Kommandos units, with Bomb Squigs/Distraction Grot use assigned to only one split unit.",
        ),
        ("ORK", "Super Runts"): ("Partial", "Scouts 9\" applied without leading restriction; hit/wound bonus not implemented."),
        ("ORK", "Tellyporta Tech"): ("Partial", "Deep Strike granted without leading restriction."),
        ("ORK", "Drill Boss"): ("Supported", "Leading: +1 to hit for melee attacks in the unit."),
        ("ORK", "Dead Choppy"): (
            "Supported",
            "Implemented via wargear keyword support: each additional dread klaw increases this weapon's Attacks by 1.",
        ),
        ("ORK", "Bubblechukka"): (
            "Supported",
            "Implemented via wargear keyword support: random Bubblechukka profile selection by D6 (1-2 big bubble, 3-4 wobbly bubble, 5-6 dense bubble).",
        ),
        ("ORK", "Snagged"): (
            "Supported",
            "Implemented via wargear keyword support: hits against MONSTER/VEHICLE targets grant +2 charge and prevent Fire Overwatch against the bearer until end of turn.",
        ),
        ("TAU", "BODYGUARD"): (
            "Supported",
            "Kroot Carnivores BODYGUARD enforces two attached Leaders only at Starting Strength 20 and requires those two Leaders to be different datasheets.",
        ),
        ("TAU", "INDEPENDENT POWER"): (
            "Supported",
            "Army validation enforces Commander Farsight and ETHEREAL units as mutually exclusive.",
        ),
        ("TAU", "Advanced Armour"): ("Supported", "Feel No Pain 4+ against mortal wounds."),
        ("TAU", "Agile Combatant"): ("Supported", "Shoot after Falling Back."),
        ("TAU", "Recon Drone"): ("Supported", "Infiltrators."),
        ("TYR", "Adaptable Predators"): ("Supported", "Shoot and charge after Falling Back."),
        ("TYR", "Bounding Leap"): ("Supported", "Charge-after-Advance eligibility."),
        ("TYR", "Irresistible Force"): ("Supported", "Charge-after-Fall-Back eligibility."),
        ("TYR", "Foul Spores (Aura)"): ("Partial", "Stealth aura within 6\" for non-MONSTER TYRANIDS units; Benefit of Cover aura not implemented."),
        ("TYR", "Unnatural Resilience"): ("Supported", "Feel No Pain 4+ against mortal wounds."),
        ("TYR", "Singular Purpose"): (
            "Supported",
            "BR1: select one enemy unit for source-model Hit/Wound re-rolls for the battle, or one objective marker for source-model conditional Feel No Pain 5+ and Objective Control 15 while in range.",
        ),
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
        ("TS", "Aetherstride (Psychic)"): (
            "Supported",
            "Movement phase setup prompt supports 6\" Deep Strike placement, prevents charging that turn, and grants Sustained Hits D3 to Dark Blessing until turn end.",
        ),
        ("TS", "Impossible Form (Psychic)"): (
            "Supported",
            "Unearthly Power selection enables -1 Damage for attacks allocated to this model.",
        ),
        ("TS", "Sacrificial Blessing"): (
            "Supported",
            "When selected to shoot/fight while leading: optional use destroys one bodyguard model and grants D3 Attacks and D3 Strength to the model's Psychic weapons until end of phase.",
        ),
        ("TS", "Time Flux (Aura, Psychic)"): (
            "Supported",
            "Unearthly Power selection enables a 6\" aura that grants +2\" Move to friendly THOUSAND SONS units.",
        ),
        ("TS", "Treason of Tzeentch (Psychic)"): (
            "Supported",
            "Unearthly Power selection enables start-of-opponent Shooting phase target selection that makes the target unit's ranged weapons Hazardous until end of phase.",
        ),
        ("TS", "Twisted Sorceries (Psychic)"): (
            "Supported",
            "Once per battle in Shooting/Fight: optional use grants +3 Attacks and +3 Strength to the model's Psychic weapons until end of phase.",
        ),
        ("TS", "Unearthly Power"): (
            "Supported",
            "Start of battle round: choose one Crimson King ability (Impossible Form, Treason of Tzeentch, or Time Flux) active until the start of the next battle round.",
        ),
        ("TS", "Ambushing Hunters"): (
            "Supported",
            "End of opponent turn: optional Strategic Reserves move while more than 6\" horizontally from enemies.",
        ),
        ("TS", "Binding Tendrils (Psychic)"): (
            "Supported",
            "After shooting with Arcane Fire, hit enemy unit is pinned/ensnared: -2 Move and -2 to Charge rolls until next turn.",
        ),
        ("TS", "Arch-Sorcerer of Tzeentch (Psychic)"): (
            "Supported",
            "When this model attempts a Ritual, add 1 to the Psychic test result.",
        ),
        ("TS", "Lord of the Planet of the Sorcerers (Psychic)"): (
            "Supported",
            "This model can attempt up to two Rituals per turn and adds 2 to each Ritual Psychic test result.",
        ),
        ("TS", "Immaterial Flare (Aura)"): (
            "Supported",
            "Friendly Thousand Sons Psykers within 6\" gain +1 to Channel-the-Warp Psychic tests; bonus does not stack with other test modifiers.",
        ),
        ("TS", "Spirit Snare"): (
            "Supported",
            "When a nearby Thousand Sons Cabal Psyker model is destroyed, choose a Spirit Snare model within 9\" to gain +1 Ritual test bonus (capped at +2).",
        ),
        ("TS", "Rebind Rubricae (Psychic)"): (
            "Supported",
            "Command phase while leading: roll D6 table (1: D3 mortal wounds to unit, 2-5: return 1 Bodyguard model, 6: return up to 2 Bodyguard models).",
        ),
        ("TS", "Herd Banner"): (
            "Supported",
            "While the bearer's unit controls an objective within range, improve Leadership by 1.",
        ),
        ("TS", "Hunter of Souls"): (
            "Supported",
            "Attacks vs CHARACTER units re-roll hit/wound rolls of 1 (full re-rolls vs PSYKER CHARACTER); destroying those units heals this model (D3 or 3).",
        ),
        ("TS", "Terrifying Assault"): (
            "Supported",
            "After this model shoots or fights, select a hit enemy unit for a Battle-shock test, with an additional -1 modifier while it is within 9\" of friendly Thousand Sons Psyker units.",
        ),
        ("TS", "Destroyer of Futures"): (
            "Supported",
            "Fire Overwatch hits on 5+, or 4+ when the target is within 9\" of one or more friendly Thousand Sons Psyker units.",
        ),
        ("TS", "Ensorcelled Annihilation"): (
            "Supported",
            "Ranged attacks vs MONSTER/VEHICLE units hit by Thousand Sons Psychic attacks this phase can re-roll Hit and Damage rolls.",
        ),
        ("TS", "Ensorcelled Destruction"): (
            "Supported",
            "Ranged attacks vs non-MONSTER/VEHICLE units hit by Thousand Sons Psychic attacks this phase gain +1 Strength and +1 AP.",
        ),
        ("TS", "Flame-wreathed"): (
            "Supported",
            "After ending a Normal move over an enemy unit, select that moved-over unit; it cannot gain Benefit of Cover until end of turn.",
        ),
        ("TS", "Bringers of Change"): (
            "Supported",
            "Ranged attacks re-roll wound rolls of 1; full wound re-rolls while targeting units within range of uncontrolled objectives.",
        ),
        ("TS", "Glimpse of Eternity (Psychic)"): (
            "Supported",
            "Model can change one Hit/Wound/Save roll to an unmodified 6 (once per round/turn parser support).",
        ),
        ("TS", "Marked by Fate (Psychic)"): (
            "Supported",
            "Start of Shooting phase: select a visible enemy unit; this unit gains +1 to hit against that target until end of phase.",
        ),
        ("TS", "One Head Looks Back (Aura)"): (
            "Supported",
            "Opponent targeted Stratagem CP increase aura within 12\".",
        ),
        ("TS", "Prophesied Doom"): (
            "Supported",
            "After ending a charge move, roll one D6 per model and inflict 1 mortal wound on each 4+.",
        ),
        ("TS", "Prophetic Sentinels"): (
            "Supported",
            "Once per battle round, this unit can be targeted by Fire Overwatch or Heroic Intervention for 0CP.",
        ),
        ("TS", "Regenerating Monstrosities"): (
            "Supported",
            "Start of each Command phase: one model in the unit regains up to 3 lost wounds.",
        ),
        ("TS", "Rites of Coalescence"): (
            "Supported",
            "While unit contains a PSYKER model, incoming attacks suffer -1 to Wound rolls.",
        ),
        ("TS", "Scryer of Fates (Psychic)"): (
            "Supported",
            "After deployment, redeploy up to three units; selected units can be placed into Strategic Reserves regardless of current limits.",
        ),
        ("TS", "Siege Shield"): (
            "Supported",
            "Demolisher cannon can target units in Engagement Range and ignores Hit penalty while engaged.",
        ),
        ("TS", "Snarling Protector"): (
            "Supported",
            "Heroic Intervention can target this model for 0CP even if already used this phase; charge rolls can be re-rolled when charging enemies engaging Thousand Sons Psykers.",
        ),
        ("TS", "Sorcerous Support"): (
            "Supported",
            "After this model shoots, select a hit enemy unit; disembarked models from this transport gain +1 to Hit and +1 to Wound with Psychic attacks against that target this phase.",
        ),
        ("QI", "Paladin's Duty (Bondsman)"): (
            "Supported",
            "Bondsman effect: affected models gain [LETHAL HITS], and their melee weapons gain [LANCE].",
        ),
        ("QI", "Warden's Duty (Bondsman)"): (
            "Supported",
            "Bondsman effect: affected models gain [SUSTAINED HITS 1], and their ranged weapons gain [IGNORES COVER].",
        ),
        ("QI", "Errant's Duty (Bondsman)"): (
            "Supported",
            "Bondsman effect: affected models can re-roll Advance rolls, and their ranged weapons gain [ASSAULT].",
        ),
        ("QI", "Mentor (Bondsman)"): (
            "Supported",
            "Bondsman effect: affected models can re-roll Wound rolls against the Bondsman source model's quarry.",
        ),
        ("QI", "Gallant's Duty (Bondsman)"): (
            "Supported",
            "Bondsman effect: affected models can re-roll Charge rolls, and can re-roll Hit rolls for melee attacks.",
        ),
        ("QI", "Defender's Duty (Bondsman)"): (
            "Supported",
            "Bondsman effect: when an attack is allocated to an affected model, subtract 1 from the attack's Damage characteristic.",
        ),
        ("QI", "Crusader's Duty (Bondsman)"): (
            "Supported",
            "Bondsman effect: affected models add 1 to Hit rolls for ranged attacks.",
        ),
        ("QI", "Exemplar of the Code"): (
            "Supported",
            "Start-of-battle quarry selection; attacks vs quarry can re-roll Wound rolls; when quarry is destroyed you can optionally select a new quarry.",
        ),
        ("QI", "Selfless Protector"): (
            "Supported",
            "Ranged attacks allocated to friendly IMPERIAL KNIGHTS models that are not fully visible because of this Knight Defender model gain Benefit of Cover and a 4+ invulnerable save.",
        ),
        ("QI", "Data-spike"): (
            "Supported",
            "Start of Fight phase: optional engaged enemy VEHICLE selection; on 4+ it suffers D6 mortal wounds and its melee weapon Weapon Skill is worsened by 1 until end of phase.",
        ),
        ("QI", "Thundershock"): (
            "Supported",
            "When selecting targets for thundercoil harpoon, roll for the target and nearby enemy units; each unit that rolls 4+ suffers D3 mortal wounds after attacks against the target are resolved.",
        ),
        ("QI", "USING SIR HEKHTUR"): (
            "Supported",
            "When Canis Rex is destroyed, Sir Hekhtur is spawned and must Emergency Disembark as if from a destroyed Transport; Sir Hekhtur can only be targeted by Core Stratagems; Canis Rex unit-destroyed handling is deferred until Sir Hekhtur is destroyed.",
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
        ("DG", "DEPLOYMENT", "000002462"): (
            "Supported",
            "Miasmic Malignifier deployment is represented by standard fortification setup in the engine; the two-piece terrain representation is abstracted to a single fortification unit for gameplay effects.",
        ),
        ("AM", "DEPLOYMENT", "000002619"): (
            "Supported",
            "Aegis Defence Line deployment enforces section composition limits and connectivity, including the broken-shield 1/2\" middle-pair exception, while treating all sections as one model.",
        ),
        ("GC", "DEPLOYMENT", "000003955"): (
            "Supported",
            "Aegis Defence Line deployment enforces section composition limits and connectivity, including the broken-shield 1/2\" middle-pair exception, while treating all sections as one model.",
        ),
        ("NEC", "DEPLOYMENT", "000002361"): (
            "Supported",
            "Convergence Of Dominion setup uses a 12\" model-to-model chain (instead of unit coherency) and then splits into single-model units so each Starstele is treated as a separate unit for the rest of the battle.",
        ),
        ("NEC", "TRIARCHAL MENHIRS", "000002360"): (
            "Supported",
            "When this unit's Szarekh model is destroyed, all remaining TRIARCHAL MENHIR models in the unit are also destroyed.",
        ),
        ("ORK", "BODYGUARD", "000000016"): (
            "Supported",
            "Boyz BODYGUARD enforces two attached Leaders only at Starting Strength 20 and requires one attached Leader to have the WARBOSS keyword when two Leaders are attached.",
        ),
        ("ORK", "PATROL SQUAD", "000000025"): (
            "Supported",
            "Declare Battle Formations: optional split into two 5-model Kommandos units, with Bomb Squigs/Distraction Grot use assigned to only one split unit.",
        ),
        ("TAU", "BODYGUARD", "000000413"): (
            "Supported",
            "Kroot Carnivores BODYGUARD enforces two attached Leaders only at Starting Strength 20 and requires those two Leaders to be different datasheets.",
        ),
        ("TAU", "INDEPENDENT POWER", "000000406"): (
            "Supported",
            "Army validation enforces Commander Farsight and ETHEREAL units as mutually exclusive.",
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


def _detachment_ability_support_by_id() -> Dict[str, Tuple[str, str]]:
    return {
        "000009125": (
            "Supported",
            "Ordo Xenos Alien Hunters: Deathwatch Mission Tactics command-phase choice is fully implemented (Furor: Sustained Hits 1, Malleus: Lethal Hits, Purgatus: Precision on critical wounds) for DEATHWATCH units, with each tactic selectable once per battle.",
        ),
        "000009129": (
            "Supported",
            "Ordo Hereticus Purgation Force: Root out Heresy grants [IGNORES COVER] to ranged weapons of ADEPTUS ARBITES/INQUISITOR/INQUISITORIAL AGENTS/ORDO HERETICUS models and grants [SUSTAINED HITS 1] when those models attack CHAOS units containing 5+ models.",
        ),
        "000009133": (
            "Supported",
            "Ordo Malleus Daemon Hunters: Destroy the Daemonic grants re-roll Hit rolls of 1 for INQUISITOR/INQUISITORIAL AGENTS/ORDO MALLEUS model attacks, and grants re-roll Wound rolls of 1 as well when those attacks target DAEMON units.",
        ),
        "000009137": (
            "Supported",
            "Imperialis Fleet: At all Costs command-phase choice fully implemented with Eliminate target selection (+1 to hit vs selected enemy unit) and Acquire objective selection (+1 Objective Control, +1 Leadership improvement, and 5+ invulnerable save while in range) until your next Command phase.",
        ),
        "000010711": (
            "Supported",
            "Freebooter Krew: Here Be Loot objective selection and Sustained Hits 1 objective-range attack gating implemented.",
        ),
        "000008875": (
            "Supported",
            "Dread Mob: Try Dat Button! selection and effect resolution implemented, including manual Hazardous multi-source fail-on-2 handling.",
        ),
        "000008876": (
            "Supported",
            "Dread Mob: Gretchin units from your army gain the Battleline keyword.",
        ),
        "000008980": (
            "Supported",
            "Chaos Cult: TRAITOR GUARDSMEN SQUAD units from your army gain the BATTLELINE keyword.",
        ),
        "000008880": (
            "Supported",
            "Green Tide: BOYZ units gain a 6+ invulnerable save when targeted, improving to 5+ while the unit contains 10 or more models.",
        ),
        "000008871": (
            "Supported",
            "Kult of Speed: SPEED FREEKS units are eligible to shoot and declare a charge in turns when they Advanced or Fell Back.",
        ),
        "000009990": (
            "Supported",
            "More Dakka!: ORKS INFANTRY/WALKER ranged weapons count as ASSAULT, and while Waaagh! is active during your Shooting phase those models' ranged attacks gain Sustained Hits 1.",
        ),
        "000009794": (
            "Supported",
            "Taktikal Brigade: each Boss Snikrot/Mek/Warboss model can issue one once-per-battle-round Taktik choice (or none) in your Command phase or after Reinforcements setup in your Movement phase; selected friendly ORKS unit within 6\" takes a Leadership test for the issuing model (failure inflicts 1 mortal wound) and gains one Taktik until your next Command phase (Get Stuck In charge re-rolls, Get On Wiv It +1 melee Strength, Sneaky Stalkin' Stealth + model-level Benefit of Cover excluding Meganobz, Shoota Drills +1 ranged hit for INFANTRY/MOUNTED models), with Battle-shock gating and Stormboyz gaining Battleline.",
        ),
        "000008820": (
            "Supported",
            "Kroot Hunting Pack: Kroot Carnivore units from your army gain the Battleline keyword.",
        ),
    }


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
    for det_id, val in _detachment_ability_support_by_id().items():
        det_key = str(det_id or "").strip()
        if det_key:
            ABILITY_SUPPORT_BY_ID[det_key] = val

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
    if not str(description or "").strip():
        restriction_support = _restriction_support_by_name().get(_norm(name or ""))
        if restriction_support:
            return restriction_support

    desc_support = _warlord_enhancement_restriction_support(description)
    unique_model_support = _unique_model_restriction_support(description)
    inspiring_commander_support = _inspiring_commander_support(description)
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
    if inspiring_commander_support:
        return inspiring_commander_support
    if chapter_restriction_support:
        return chapter_restriction_support
    closest_m_veh_support = _closest_monster_vehicle_reroll_support(description)
    monster_vehicle_reroll_support = _monster_vehicle_reroll_support(description)
    unit_contains_oc_support = _unit_contains_oc_support(description)
    aura_oc_support = _aura_objective_control_support(description)
    aura_benefit_of_cover_support = _aura_benefit_of_cover_support(description)
    enemy_aura_oc_penalty_support = _enemy_aura_objective_control_penalty_support(description)
    aura_adv_charge_support = _aura_advance_charge_roll_support(description)
    aura_hit_support = _aura_hit_bonus_support(description)
    aura_strength_support = _aura_strength_support(description)
    aura_toughness_support = _aura_toughness_support(description)
    aura_melee_ap_support = _aura_melee_ap_support(description)
    fall_back_shoot_support = _fall_back_shoot_support(description)
    advance_no_roll_phase_move_support = _advance_no_roll_with_phase_move_support(description)
    advance_no_roll_support = _advance_no_roll_fixed_distance_support(description)
    movement_ignore_vertical_support = _movement_ignore_vertical_distance_support(description)
    charge_move_devastating_support = _charge_move_devastating_wounds_support(description)
    charge_move_profile_attacks_support = _charge_move_model_weapon_profile_attacks_bonus_support(description)
    defensive_charge_roll_penalty_support = _defensive_charge_roll_penalty_support(description)
    phase_move_support = _leading_unit_phase_move_support(description)
    phase_terrain_support = _leading_unit_move_and_phase_terrain_support(description)
    move_over_friendly_support = _move_over_friendly_monster_vehicle_support(description)
    move_over_low_terrain_support = _move_over_low_terrain_support(description)
    titanic_move_through_support = _titanic_move_through_support(description)
    move_over_mortal_support = _move_over_mortal_wounds_support(description)
    floating_death_support = _floating_death_support(description)
    hazardous_test_modifier_support = _hazardous_test_modifier_support(description)
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
    embarking_firing_deck_weight_support = _embarking_firing_deck_weight_support(description)
    end_of_fight_embark_support = _end_of_fight_embark_support(description)
    enemy_move_reactive_d6_support = _enemy_move_reactive_d6_support(description)
    horde_move_support = _horde_move_support(description)
    setup_reactive_shoot_charge_support = _setup_reactive_shoot_or_charge_support(description)
    post_deployment_redeploy_support = _post_deployment_redeploy_support(description)
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
    shooting_phase_dice_pool_mortal_support = _shooting_phase_dice_pool_mortal_support(description)
    start_shooting_phase_vehicle_mortal_heal_support = _start_shooting_phase_vehicle_mortal_heal_support(description)
    post_shoot_battleshock_support = _post_shoot_battleshock_support(description)
    post_shoot_afflicted_support = _post_shoot_afflicted_support(description)
    post_shoot_shoot_again_support = _post_shoot_shoot_again_support(description)
    post_shoot_disembark_wound_reroll_support = _post_shoot_disembark_wound_reroll_support(description)
    post_shoot_ap_bonus_support = _post_shoot_ap_bonus_support(description)
    post_shoot_infantry_mortal_support = _post_shoot_infantry_mortal_wounds_battleshock_support(description)
    post_shoot_wracking_agonies_support = _post_shoot_wracking_agonies_support(description)
    post_shoot_suppression_support = _post_shoot_suppression_support(description)
    post_shoot_reactive_move_no_charge_support = _post_shoot_reactive_move_no_charge_support(description)
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
    start_any_phase_unit_invuln_support = _start_any_phase_unit_invuln_support(description)
    start_any_phase_unit_fnp_support = _start_any_phase_unit_fnp_support(description)
    reanimation_dice_reroll_support = _reanimation_dice_reroll_support(description)
    reanimation_additional_d3_aura_support = _reanimation_additional_d3_aura_support(description)
    reanimation_additional_one_once_per_battle_round_support = _reanimation_additional_one_once_per_battle_round_support(description)
    repair_barge_reanimation_support = _repair_barge_reanimation_support(description)
    command_phase_end_mortal_table_support = _command_phase_end_enemy_within_range_mortal_table_support(description)
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
    order_range_extension_support = _order_range_extension_support(description)
    act_of_faith_cherub_support = _act_of_faith_cherub_support(description)
    ammo_runt_support = _ammo_runt_support(description)
    bomb_squigs_support = _bomb_squigs_support(description)
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
    model_closest_target_ap_bonus_support = _model_closest_target_ap_bonus_support(description)
    model_stationary_ranged_sustained_support = _model_stationary_ranged_sustained_hits_support(description)
    model_stationary_weapon_keyword_support = _model_stationary_weapon_keyword_support(description)
    ordered_stationary_heavy_sustained_support = _ordered_stationary_heavy_sustained_hits_support(description)
    targeted_stratagem_refund_support = _targeted_stratagem_cp_refund_support(description)
    targeted_stratagem_discount_support = _targeted_stratagem_cp_discount_support(description)
    targeted_stratagem_increase_support = _targeted_stratagem_cp_increase_support(description)
    overwatch_hit_threshold_support = _overwatch_hit_threshold_support(description)
    brutal_example_overwatch_support = _brutal_example_overwatch_support(description)
    charge_end_mortal_support = _charge_end_mortal_wounds_support(description)
    start_fight_phase_self_destruction_support = _start_fight_phase_self_destruction_support(description)
    shooting_target_arcing_mortals_support = _shooting_target_arcing_mortals_support(description)
    fight_within_3_support = _fight_within_3_support(description)
    allocated_damage_reduction_support = _allocated_damage_reduction_support(description)
    allocated_damage_zero_support = _allocated_damage_set_zero_support(description)
    ranged_ignore_bs_hit_support = _ranged_ignore_bs_hit_modifiers_support(description)
    ranged_ignore_hit_support = _ranged_ignore_hit_modifiers_support(description)
    ignore_skill_and_hit_modifiers_support = _ignore_skill_and_hit_modifiers_support(description)
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
    if floating_death_support:
        return floating_death_support
    if hazardous_test_modifier_support:
        return hazardous_test_modifier_support
    if ranged_ignore_bs_hit_support:
        return ranged_ignore_bs_hit_support
    if ranged_ignore_hit_support:
        return ranged_ignore_hit_support
    if ignore_skill_and_hit_modifiers_support:
        return ignore_skill_and_hit_modifiers_support
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
    if aura_benefit_of_cover_support:
        return aura_benefit_of_cover_support
    if enemy_aura_oc_penalty_support:
        return enemy_aura_oc_penalty_support
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
    if advance_no_roll_phase_move_support:
        return advance_no_roll_phase_move_support
    if advance_no_roll_support:
        return advance_no_roll_support
    if movement_ignore_vertical_support:
        return movement_ignore_vertical_support
    if charge_move_devastating_support:
        return charge_move_devastating_support
    if charge_move_profile_attacks_support:
        return charge_move_profile_attacks_support
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
    if ammo_runt_support:
        return ammo_runt_support
    if bomb_squigs_support:
        return bomb_squigs_support
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
    if embarking_firing_deck_weight_support:
        return embarking_firing_deck_weight_support
    if enemy_move_reactive_d6_support:
        return enemy_move_reactive_d6_support
    if horde_move_support:
        return horde_move_support
    if setup_reactive_shoot_charge_support:
        return setup_reactive_shoot_charge_support
    if post_deployment_redeploy_support:
        return post_deployment_redeploy_support
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
    if shooting_phase_dice_pool_mortal_support:
        return shooting_phase_dice_pool_mortal_support
    if start_shooting_phase_vehicle_mortal_heal_support:
        return start_shooting_phase_vehicle_mortal_heal_support
    if post_shoot_battleshock_support:
        return post_shoot_battleshock_support
    if post_shoot_afflicted_support:
        return post_shoot_afflicted_support
    if post_shoot_shoot_again_support:
        return post_shoot_shoot_again_support
    if post_shoot_disembark_wound_reroll_support:
        return post_shoot_disembark_wound_reroll_support
    if post_shoot_ap_bonus_support:
        return post_shoot_ap_bonus_support
    if post_shoot_infantry_mortal_support:
        return post_shoot_infantry_mortal_support
    if post_shoot_wracking_agonies_support:
        return post_shoot_wracking_agonies_support
    if post_shoot_suppression_support:
        return post_shoot_suppression_support
    if post_shoot_reactive_move_no_charge_support:
        return post_shoot_reactive_move_no_charge_support
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
    if start_any_phase_unit_invuln_support:
        return start_any_phase_unit_invuln_support
    if start_any_phase_unit_fnp_support:
        return start_any_phase_unit_fnp_support
    if reanimation_dice_reroll_support:
        return reanimation_dice_reroll_support
    if reanimation_additional_d3_aura_support:
        return reanimation_additional_d3_aura_support
    if reanimation_additional_one_once_per_battle_round_support:
        return reanimation_additional_one_once_per_battle_round_support
    if repair_barge_reanimation_support:
        return repair_barge_reanimation_support
    if command_phase_end_mortal_table_support:
        return command_phase_end_mortal_table_support
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
    if order_range_extension_support:
        return order_range_extension_support
    if act_of_faith_cherub_support:
        return act_of_faith_cherub_support
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
    if model_closest_target_ap_bonus_support:
        return model_closest_target_ap_bonus_support
    if model_stationary_ranged_sustained_support:
        return model_stationary_ranged_sustained_support
    if model_stationary_weapon_keyword_support:
        return model_stationary_weapon_keyword_support
    if ordered_stationary_heavy_sustained_support:
        return ordered_stationary_heavy_sustained_support
    if targeted_stratagem_refund_support:
        return targeted_stratagem_refund_support
    if targeted_stratagem_discount_support:
        return targeted_stratagem_discount_support
    if targeted_stratagem_increase_support:
        return targeted_stratagem_increase_support
    if overwatch_hit_threshold_support:
        return overwatch_hit_threshold_support
    if brutal_example_overwatch_support:
        return brutal_example_overwatch_support
    if shooting_target_arcing_mortals_support:
        return shooting_target_arcing_mortals_support
    if charge_end_mortal_support:
        return charge_end_mortal_support
    if start_fight_phase_self_destruction_support:
        return start_fight_phase_self_destruction_support
    if fight_within_3_support:
        return fight_within_3_support
    if allocated_damage_zero_support:
        return allocated_damage_zero_support
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
    warlord_clause = (
        r"(?:this|that|the)?\s*(?:unit|model|models|bearer)?\s*"
        r"(?:cannot be(?: selected as)? your|none of these models can be(?: selected as)? your)\s+warlord"
    )
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
    if re.search(pattern, norm):
        return ("Supported", "Space Marine chapter restriction enforced during army validation.")
    return None


def _unique_model_restriction_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    this_model_pattern = r"(?:unless otherwise stated )?you cannot include more than one of this (?:model|unit) in your army"
    if re.fullmatch(this_model_pattern, norm):
        return ("Supported", "Army validation enforces unique inclusion for this model.")

    named_unit_pattern = (
        r"your army cannot include more than "
        r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve) "
        r".+ units?"
    )
    if re.fullmatch(named_unit_pattern, norm):
        return ("Supported", "Army validation enforces named-unit inclusion caps.")
    return None


def _inspiring_commander_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"if you include this model in your army until the end of the battle "
        r"non character models in .+ units? from your army have an objective control "
        r"characteristic of \d+ while they are not battle shocked"
    )
    if re.fullmatch(pattern, norm):
        return (
            "Supported",
            "Army-wide named-unit Objective Control set parsed (non-CHARACTER models only; disabled while the target unit is Battle-shocked).",
        )
    return None


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
    if re.search(r"while (?:this model|this unit|(?:the )?bearer) is leading a unit", low, flags=re.IGNORECASE):
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

    base_fnp_value: Optional[str] = None
    m = re.search(
        r"(?:models?\s+in\s+)?(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit)\s+"
        r"(?:have|has)\s+(?:a\s+|the\s+)?feel\s+no\s+pain\s*([1-6])\+?(?:\s+ability)?",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        base_fnp_value = m.group(1)
        match_text = m.group(0)
        if leading_prefix:
            notes.append(f"{leading_prefix}Feel No Pain {m.group(1)}+.")
        elif "bearer" in match_text:
            notes.append(f"Bearer's unit gains Feel No Pain {m.group(1)}+.")
        else:
            notes.append(f"Unit gains Feel No Pain {m.group(1)}+.")

    m = re.search(
        r"if\s+(?:the\s+)?(?:bearer'?s\s+unit|that\s+unit|this\s+unit)\s+has\s+(?:the\s+)?(?P<keyword>[a-z0-9][a-z0-9 '\-]*)\s+keyword,?\s*"
        r"models?\s+in\s+(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit)\s+have\s+(?:a\s+|the\s+)?feel\s+no\s+pain\s*(?P<value>[1-6])\+?(?:\s+ability)?\s+instead",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        keyword = str(m.group("keyword") or "").strip().upper()
        value = str(m.group("value") or "").strip()
        if leading_prefix and base_fnp_value:
            notes.append(
                f"{leading_prefix}Feel No Pain improves to {value}+ while the unit has the {keyword} keyword."
            )
        elif leading_prefix:
            notes.append(f"{leading_prefix}Feel No Pain {value}+ while the unit has the {keyword} keyword.")
        elif base_fnp_value:
            notes.append(f"Bearer's unit Feel No Pain improves to {value}+ while it has the {keyword} keyword.")
        else:
            notes.append(f"Unit gains Feel No Pain {value}+ while it has the {keyword} keyword.")

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
        r"models?\s+in\s+(?:the\s+bearer'?s\s+unit|that\s+unit|this\s+unit)\s+have\s+the\s+deep\s+strike\s+ability",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        match_text = m.group(0)
        if leading_prefix:
            notes.append(f"{leading_prefix}unit gains Deep Strike.")
        elif "bearer" in match_text:
            notes.append("Bearer's unit gains Deep Strike.")
        else:
            notes.append("Unit gains Deep Strike.")

    m = re.search(
        r"(?:(melee|ranged)\s+)?weapons?\s+equipped\s+by\s+models\s+in\s+(?:the\s+bearer'?s\s+unit|that\s+unit).*?"
        r"sustained\s+hits\s*(\d+)",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        scope = (m.group(1) or "").strip().lower()
        val = m.group(2)
        has_lance = bool(
            re.search(
                r"(?:(melee|ranged)\s+)?weapons?\s+equipped\s+by\s+models\s+in\s+(?:the\s+bearer'?s\s+unit|that\s+unit).*?lance",
                low,
                flags=re.IGNORECASE,
            )
        )
        kw_text = f"Sustained Hits {val} and Lance" if has_lance else f"Sustained Hits {val}"
        if scope:
            if leading_prefix:
                notes.append(f"{leading_prefix}{scope} weapons gain {kw_text}.")
            else:
                notes.append(f"Bearer's unit {scope} weapons gain {kw_text}.")
        else:
            if leading_prefix:
                notes.append(f"{leading_prefix}weapons gain {kw_text}.")
            else:
                notes.append(f"Bearer's unit weapons gain {kw_text}.")

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

    m = re.search(
        r"each\s+time\s+(?:the\s+bearer'?s\s+unit|this\s+model'?s\s+unit|this\s+unit|that\s+unit|your\s+unit)\s+"
        r"(?:consolidates|makes\s+a\s+consolidation\s+move)\s*,?\s*"
        r"(?:it|models\s+in\s+(?:it|that\s+unit|this\s+unit|your\s+unit|the\s+bearer'?s\s+unit)|"
        r"each\s+model\s+in\s+(?:it|that\s+unit|this\s+unit|your\s+unit|the\s+bearer'?s\s+unit))\s+can\s+move\s+"
        r"an?\s+additional\s+(\d+)\s*\"?\s+"
        r"(?:provided|as\s+long\s+as)\s+(?:your\s+unit|that\s+unit|this\s+unit)\s+(?:can\s+end|ends)\s+"
        r"that\s+(?:consolidation\s+)?move\s+within\s+engagement\s+range\s+of\s+one\s+or\s+more\s+enemy\s+units?",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        try:
            extra = int(m.group(1))
        except Exception:
            extra = 0
        if extra > 0:
            total = 3 + extra
            if leading_prefix:
                notes.append(f"{leading_prefix}Consolidate up to {total}\" when ending in Engagement Range.")
            else:
                notes.append(f"Consolidate up to {total}\" when ending in Engagement Range.")
    normalized_sentences = []
    for sentence in re.split(r"[.;]\s*", _strip_html(description)):
        norm_sentence = _norm_rules_text(sentence)
        if norm_sentence:
            normalized_sentences.append(norm_sentence)

    lead_prefix = r"(?:(?:while (?:this model|this unit|(?:the )?bearer) is leading a unit )?)"
    unit_ref = r"(?:the )?(?:bearers|that|this|your) unit"
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
        rf"{lead_prefix}if {unit_ref} has (?:the )?[a-z0-9][a-z0-9 '\-]* keyword models? in {unit_ref} have (?:a|the)? feel no pain [1-6](?: ability)? instead",
        rf"{lead_prefix}{unit_ref} has (?:a|the)? feel no pain [1-6](?: ability)?",
        rf"{lead_prefix}{unit_ref} has (?:a|the)? feel no pain [1-6](?: ability)? against psychic attacks",
        rf"{lead_prefix}{unit_ref} has (?:a|the)? feel no pain [1-6](?: ability)? against psychic attacks and mortal wounds?",
        rf"{lead_prefix}{unit_ref} has (?:a|the)? feel no pain [1-6](?: ability)? against mortal wounds?",
        rf"{lead_prefix}{unit_ref} has (?:a|the)? feel no pain [1-6](?: ability)? against mortal wounds? and psychic attacks",
        rf"{lead_prefix}(?:you can )?reroll advance rolls? made for {unit_ref} and you can reroll any rolls made for {unit_ref} while it is performing an agile (?:manoeuvre|maneuver)",
        rf"{lead_prefix}models? in {unit_ref} have (?:a|the)? [1-6] invulnerable save",
        rf"{lead_prefix}{unit_ref} has (?:a|the)? [1-6] invulnerable save",
        rf"{lead_prefix}models? in {unit_ref} have the deep strike ability",
        rf"{lead_prefix}(?:melee |ranged )?weapons equipped by models in {unit_ref} have the sustained hits \d+ ability",
        rf"{lead_prefix}(?:melee |ranged )?weapons equipped by models in {unit_ref} have the sustained hits \d+ and lance abilities",
        rf"{lead_prefix}add \d+ to the range characteristic of melta weapons equipped by models in {unit_ref}",
        rf"{lead_prefix}(?:melee |ranged )?(?:weapons equipped by models in|attacks made by models in) {unit_ref} .* ignores cover(?: ability)?",
        rf"{lead_prefix}each time (?:a|an) (?:melee |ranged )?attack targets {unit_ref} subtract 1 from the hit roll",
        rf"{lead_prefix}(?:while|if) {unit_ref} is within range of (?:an|one or more) objective marker(?:s)?(?: you control)? each time "
        rf"(?:a|an) (?:melee |ranged )?attack targets {unit_ref} models in (?:it|{unit_ref}) have the benefit of cover(?: against that attack)?",
        rf"{lead_prefix}each time (?:a|an) (?:melee |ranged )?attack targets {unit_ref} models in (?:it|{unit_ref}) have the benefit of cover(?: against that attack)?",
        rf"{lead_prefix}each time {unit_ref} (?:consolidates|makes a consolidation move) "
        rf"(?:it|models in (?:it|{unit_ref})|each model in (?:it|{unit_ref})) can move an additional \d+ "
        rf"(?:provided|as long as) {unit_ref} (?:can end|ends) that (?:consolidation )?move within engagement range of one or more enemy units",
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
    if not (
        "each time a model in this unit makes a ranged attack" in norm
        or "each time this model makes a ranged attack" in norm
        or "each time a ranged attack made by this model" in norm
    ):
        return None
    if "closest" in norm:
        return None
    if "reroll" not in norm:
        return None
    if not re.search(
        r"(?:targets?|allocated to) (?:an? )?(?:enemy )?monster or vehicle (?:unit|model)",
        norm,
    ):
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


def _aura_benefit_of_cover_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    patterns = (
        r"while a friendly (?P<target>.+?) (?:unit|model) is within (?P<rng>\d+) of this (?:model|unit|the bearer) "
        r"each time a ranged attack targets that model it has the benefit of cover(?: against that attack)?",
        r"while a friendly (?P<target>.+?) (?:unit|model) is within (?P<rng>\d+) of this (?:model|unit|the bearer) "
        r"each time a ranged attack is allocated to a model in that unit that model has the benefit of cover(?: against that attack)?",
        r"while a friendly (?P<target>.+?) (?:unit|model) is within (?P<rng>\d+) of this (?:model|unit|the bearer) "
        r"each time a ranged attack targets that unit models in that unit have the benefit of cover(?: against that attack)?",
    )
    match = None
    for pattern in patterns:
        match = re.fullmatch(pattern, norm)
        if match:
            break
    if not match:
        return None
    target = str(match.group("target") or "").strip()
    rng = str(match.group("rng") or "").strip()
    return ("Supported", f"Aura: friendly {target} within {rng}\" gain Benefit of Cover against ranged attacks.")


def _enemy_aura_objective_control_penalty_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"while an enemy unit(?: excluding (?P<exclude>.+?))? is within (?P<rng>\d+) of "
        r"(?P<src>this model|this unit|the bearer|one or more units with this ability) "
        r"subtract (?P<amt>\d+) from the objective control characteristic of models in that (?:enemy unit|unit)"
        r"(?: to a minimum of (?P<ocmin>\d+))?",
        norm,
    )
    if not m:
        return None
    rng = m.group("rng")
    amt = m.group("amt")
    src = m.group("src")
    exclude = (m.group("exclude") or "").strip()
    oc_min = (m.group("ocmin") or "").strip()
    bits = [f"Enemy units within {rng}\" of {src} suffer Objective Control -{amt}."]
    if exclude:
        bits.append(f"Exclusions respected: {exclude}.")
    if oc_min:
        bits.append(f"Minimum Objective Control floor {oc_min} enforced.")
    return ("Supported", " ".join(bits))


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

    def _parse_keyword_labels(text_value: str) -> List[str]:
        normalized = re.sub(r"\s+", " ", str(text_value or "")).strip().lower()
        if not normalized:
            return []
        labels: List[str] = []
        patterns_local = (
            r"anti [a-z0-9 \-]+ \d+",
            r"sustained hits (?:d3|d6|\d+)",
            r"devastating wounds",
            r"ignores cover",
            r"twin linked",
            r"twin-linked",
            r"lethal hits",
            r"precision",
            r"lance",
            r"heavy",
        )
        for pat in patterns_local:
            for m in re.finditer(pat, normalized, flags=re.IGNORECASE):
                token = str(m.group(0) or "").strip().lower().replace("twin linked", "twin-linked")
                if not token:
                    continue
                label = _attack_keyword_label_from_text(token)
                if label and label not in labels:
                    labels.append(label)
        return labels

    def _join_labels(labels: List[str]) -> str:
        values = [str(v or "").strip() for v in labels if str(v or "").strip()]
        if not values:
            return ""
        if len(values) == 1:
            return values[0]
        if len(values) == 2:
            return f"{values[0]} and {values[1]}"
        return f"{', '.join(values[:-1])}, and {values[-1]}"

    patterns = [
        (
            rf"{lead_prefix}(?:(?P<scope>melee|ranged) )?weapons equipped by models in "
            r"(?:the bearers unit|that unit|this unit) (?:have|gain) (?:the )?(?P<kw_section>[a-z0-9 \-]+?) abil(?:ity|ities)",
            "unit",
        ),
        (
            rf"{lead_prefix}(?:the )?(?:bearers|this models) (?:(?P<scope>melee|ranged) )?weapons "
            r"(?:have|has|gain) (?:the )?(?P<kw_section>[a-z0-9 \-]+?) abil(?:ity|ies)",
            "bearer",
        ),
        (
            rf"{lead_prefix}(?:(?P<scope>melee|ranged) )?weapons equipped by the bearer "
            r"(?:have|has|gain) (?:the )?(?P<kw_section>[a-z0-9 \-]+?) abil(?:ity|ies)",
            "bearer",
        ),
        (
            rf"{lead_prefix}(?:(?P<scope>melee|ranged) )?weapons equipped by this model (?:have|gain) "
            r"(?:the )?(?P<kw_section>[a-z0-9 \-]+?) abil(?:ity|ies)",
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
            labels = _parse_keyword_labels(m.group("kw_section") or "")
            if not labels:
                unsupported.append(str(m.group("kw_section") or ""))
                continue
            scope = (m.group("scope") or "").strip().lower()
            scope_text = "weapons"
            if scope == "melee":
                scope_text = "melee weapons"
            elif scope == "ranged":
                scope_text = "ranged weapons"
            label_text = _join_labels(labels)
            if not label_text:
                unsupported.append(str(m.group("kw_section") or ""))
                continue
            if kind == "unit":
                notes.append(f"{prefix}Unit {scope_text} gain {label_text}.")
            elif kind == "bearer":
                notes.append(f"{prefix}Bearer's {scope_text} gain {label_text}.")
            else:
                notes.append(f"{prefix}Model {scope_text} gain {label_text}.")
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
        if rule.subject not in ("model_in_this_unit", "model_in_that_unit", "this_model"):
            return None
        rules.append(rule)
    if not rules:
        return None
    scopes = {r.scope for r in rules}
    subjects = {r.subject for r in rules}
    if subjects == {"this_model"}:
        note = "Model attack roll modifiers supported."
    elif scopes == {"leading"}:
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


def _ranged_ignore_hit_modifiers_support(description: str) -> Optional[Tuple[str, str]]:
    """
    Support for abilities that let ranged attacks ignore any/all Hit roll modifiers.

    Examples:
      "Each time the bearer makes a ranged attack, you can ignore any or all modifiers to the Hit roll."
      "Each time a model in this unit makes a ranged attack, you can ignore any or all modifiers to the Hit roll."
    """
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    if "ignore any or all modifiers" not in norm:
        return None
    if "hit roll" not in norm:
        return None
    if "ranged attack" not in norm and "ranged weapon" not in norm:
        return None
    if "ballistic skill" in norm or "weapon skill" in norm:
        return None
    if "wound roll" in norm:
        return None
    if "strength" in norm or "armour penetration" in norm or "damage" in norm:
        return None
    return ("Supported", "Ranged attacks: ignore any or all modifiers to the Hit roll.")


def _ignore_skill_and_hit_modifiers_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    if "ignore any or all modifiers" not in norm:
        return None
    if "hit roll" not in norm:
        return None
    has_bs = "ballistic skill" in norm
    has_ws = "weapon skill" in norm
    if not (has_bs or has_ws):
        return None
    leading = norm.startswith("while this model is leading a unit")
    prefix = "Leading: " if leading else ""
    if "ranged attack" in norm or "ranged weapon" in norm:
        scope = "Ranged attacks"
    elif "melee attack" in norm or "melee weapon" in norm:
        scope = "Melee attacks"
    else:
        scope = "Attacks"
    skills: List[str] = []
    if has_bs:
        skills.append("Ballistic Skill")
    if has_ws:
        skills.append("Weapon Skill")
    skill_text = " and ".join(skills)
    return ("Supported", f"{prefix}{scope}: ignore any or all modifiers to {skill_text} and Hit roll modifiers.")


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
    lead_prefix = r"(?:while this model is leading a unit )?"
    pattern = (
        rf"{lead_prefix}each time (?:this (?:model|unit)|a model in this unit|a model in that unit) makes (?:a|an) (?:(?P<scope>melee|ranged) )?attack "
        r"that targets (?P<target_clause>.+?) that attack has (?:the )?(?P<keyword>[a-z0-9 ]+) ability"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    label = _attack_keyword_label_from_text(m.group("keyword") or "")
    if not label:
        return None
    target_raw = str(m.group("target_clause") or "").strip()
    if not target_raw:
        return None
    target_raw = re.sub(r"^(?:an?|the)\s+", "", target_raw)
    target_raw = re.sub(r"^enemy\s+", "", target_raw)
    if target_raw.startswith("unit that is "):
        target_raw = target_raw[len("unit that is "):].strip()
    elif target_raw.startswith("unit that are "):
        target_raw = target_raw[len("unit that are "):].strip()
    elif target_raw.endswith(" unit"):
        target_raw = target_raw[:-5].strip()
    if not target_raw:
        target_raw = "unit"
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
    norm = _norm_rules_text(description)
    m = re.fullmatch(
        r"each time this model makes a ranged attack that targets the closest (?:eligible )?(?:enemy )?(?:target|unit) add (?P<val>\d+) to the hit roll",
        norm,
    )
    if m:
        val = str(m.group("val") or "1")
        return ("Supported", f"Model ranged attacks gain +{val} to hit when targeting the closest eligible target.")
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


def _model_closest_target_ap_bonus_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"each time this model makes a ranged attack that targets the closest (?:eligible )?(?:enemy )?(?:target|unit) "
        r"(?:improve the armour penetration characteristic of that attack by|add) (?P<val>\d+)"
        r"(?: to the armour penetration characteristic of that attack)?",
        norm,
    )
    if not m:
        return None
    val = str(m.group("val") or "1")
    return ("Supported", f"Model ranged attacks improve AP by {val} when targeting the closest eligible target.")


def _model_stationary_ranged_sustained_hits_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"(?:in|during) your movement phase if this model remains stationary until (?:the )?end of (?:the |your )?turn "
        r"ranged weapons equipped by this model have the sustained hits (?P<val>\d+|d3|d6) ability",
        norm,
    )
    if not m:
        return None
    val = str(m.group("val") or "1").upper()
    return (
        "Supported",
        f"If this model remains stationary in your Movement phase, its ranged weapons gain [SUSTAINED HITS {val}] until end of turn.",
    )


def _model_stationary_weapon_keyword_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"(?:in|during) your movement phase if this model remains stationary until (?:the )?end of (?:the |your )?turn "
        r"its (?P<weapon>[a-z0-9 ]+) has the (?P<keyword>[a-z0-9 ]+) ability",
        norm,
    )
    if not m:
        return None
    weapon = str(m.group("weapon") or "").strip()
    keyword = str(m.group("keyword") or "").strip().upper()
    if not weapon or not keyword:
        return None
    return (
        "Supported",
        f"If this model remains stationary in your Movement phase, its {weapon} gains [{keyword}] until end of turn.",
    )


def _ordered_stationary_heavy_sustained_hits_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"while this unit is being affected by an order provided it remain(?:s|ed) stationary this turn "
        r"all heavy weapons equipped by models in this unit have the sustained hits (?P<val>\d+|d3|d6) ability",
        norm,
    )
    if not m:
        return None
    val = str(m.group("val") or "1").upper()
    return (
        "Supported",
        f"While affected by an Order and after remaining stationary this turn, Heavy weapons in the unit gain [SUSTAINED HITS {val}].",
    )


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
    table_2_5 = (
        r"each time this model ends a charge move select one enemy unit within engagement range of this model "
        r"(?:then |and (?:then )?)?roll one d6 on a 2 5 that unit suffers d3 mortal wounds? on a 6 that unit suffers d3 3 mortal wounds?"
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
    if re.fullmatch(table_2_5, norm):
        return (
            "Supported",
            "Charge end: pick an engaged enemy; D6 table for mortal wounds (2-5=D3, 6=D3+3).",
        )
    if re.fullmatch(remaining_wounds, norm):
        return (
            "Supported",
            "Charge end: pick an engaged enemy; D6 per remaining wound, each 4+ inflicts 1 mortal wound (max 6).",
        )
    return None


def _start_fight_phase_self_destruction_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the start of the fight phase if this unit is within engagement range of one or more enemy units "
        r"you can select one model in this unit to destroy if you do select one enemy unit within engagement range of that model "
        r"and roll one d6 adding (?P<bonus>\d+) to the result if that unit is a vehicle "
        r"on a 2 5 that unit suffers d3 mortal wounds on a 6 that unit suffers (?P<high>\d+) mortal wounds?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    bonus = m.group("bonus") or "1"
    high = m.group("high") or "3"
    return (
        "Supported",
        f"Start of Fight phase: optional self-destruct model; D6 (+{bonus} vs VEHICLE), 2-5=D3 mortal wounds, 6+={high} mortal wounds.",
    )


def _shooting_phase_dice_pool_mortal_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase select one enemy unit within (?P<range>\d+) of and visible to this model "
        r"excluding units with the lone operative ability that are not part of an attached unit and are not within (?P<lone>\d+) of this model "
        r"and roll (?P<dice>one|two|three|four|five|six|seven|eight|nine|ten|\d+) d6 "
        r"for each (?P<threshold>\d)\+? that enemy unit suffers (?P<mw>d3|d6|\d+) mortal wounds?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    dice = str(m.group("dice") or "").upper()
    threshold = m.group("threshold") or "4"
    mw = str(m.group("mw") or "1").upper()
    range_val = m.group("range") or "18"
    lone = m.group("lone") or "12"
    return (
        "Supported",
        f"Shooting phase: pick visible enemy within {range_val}\" (Lone Operative exception {lone}\"); roll {dice}D6, each {threshold}+ inflicts {mw} mortal wounds.",
    )


def _start_shooting_phase_vehicle_mortal_heal_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the start of your shooting phase select one enemy vehicle unit within (?P<range>\d+) of this model and roll one d6 "
        r"on a (?P<threshold>\d)\+? that enemy unit suffers (?P<mw>d3|d6|\d+) mortal wounds and this model regains up to that many lost wounds?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    return (
        "Supported",
        f"Start of Shooting phase: pick enemy VEHICLE within {m.group('range')}\"; on {m.group('threshold')}+ it suffers {str(m.group('mw') or 'D3').upper()} mortal wounds and bearer heals the same amount.",
    )


def _shooting_target_arcing_mortals_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase each time you select a target for this models (?P<weapon>[a-z0-9 ]+) roll one d6 for the target unit "
        r"and one d6 for (?:each|every) other enemy unit within (?P<range>\d+) of the target unit on a (?P<threshold>\d)\+? "
        r"the unit being rolled for is struck by arcing energies after resolving all of this models attacks against the target unit "
        r"each unit struck by arcing energies suffers (?P<mw>d3|d6|\d+) mortal wounds?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    weapon = str(m.group("weapon") or "weapon").strip()
    range_val = m.group("range") or "3"
    threshold = m.group("threshold") or "5"
    mw = str(m.group("mw") or "D3").upper()
    return (
        "Supported",
        f"Shooting target selection ({weapon}): roll D6 for target and nearby enemies within {range_val}\"; on {threshold}+ mark struck units, then each struck unit suffers {mw} mortal wounds after attacks resolve.",
    )


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
    damage_ref = r"(?:the damage characteristic of that attack|that attack s damage characteristic|that attacks damage characteristic)"
    half_patterns = [
        rf"{base} (?:halve|half) {damage_ref}",
        rf"{base} {damage_ref} is halved",
        rf"{base} .* damage characteristic .* halved",
    ]
    sub_pattern = rf"{base} subtract (?P<val>\d+) from {damage_ref}"
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


def _allocated_damage_set_zero_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    patterns = (
        ("battle", r"once per battle when an attack is allocated to (?:the bearer|this model) you (?P<optional>can )?change (?:the )?damage characteristic(?: of that attack)? to 0"),
        ("battle round", r"once per battle round when an attack is allocated to (?:the bearer|this model) you (?P<optional>can )?change (?:the )?damage characteristic(?: of that attack)? to 0"),
    )
    for usage, pattern in patterns:
        m = re.fullmatch(pattern, norm)
        if not m:
            continue
        is_optional = bool(str(m.group("optional") or "").strip())
        if is_optional:
            return (
                "Supported",
                f"Once per {usage}, when an attack is allocated to the bearer/model, optional activation sets that attack's Damage to 0.",
            )
        return ("Supported", f"Once per {usage}, when an attack is allocated to the bearer/model, that attack's Damage is set to 0.")
    return None


def _targeted_stratagem_cp_discount_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    direct_patterns = [
        r"once per battle round one (?:unit|model) from your army with this ability can use it when "
        r"(?:its unit|this models unit|that models unit) is targeted with a stratagem(?: if it does)? reduce the cp cost of that "
        r"(?:use|usage) of that stratagem by 1 ?cp",
        r"once per battle round you can select one model from your army with this ability "
        r"(?:that models unit can be targeted with a stratagem|and target that models unit with a stratagem) "
        r"(?:if it does)? reduce the cp cost of that (?:use|usage) of that stratagem by 1 ?cp",
        r"once per (?P<limit>battle round|turn) when you target this (?:model|unit) with a stratagem(?: you may)? "
        r"reduce the cp cost of that (?:use|usage) of that stratagem by 1 ?cp",
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
        limit = "battle round"
        if "limit" in m.groupdict():
            parsed_limit = str(m.group("limit") or "").strip().lower()
            if parsed_limit == "turn":
                limit = "turn"
        if "keyword" in m.groupdict():
            kw = re.sub(r"\s+", " ", (m.group("keyword") or "").strip())
            rng = m.group("range") or "0"
            kw_label = kw.upper() if kw else "friendly"
            return (
                "Supported",
                f"Once per {limit}, when a friendly {kw_label} unit within {rng}\" is targeted with a Stratagem, reduce its CP cost by 1.",
            )
        subject = "this model" if "target this model with a stratagem" in norm else "this unit"
        return (
            "Supported",
            f"Once per {limit}, when {subject} is targeted with a Stratagem, you can reduce its CP cost by 1.",
        )
    return None


def _targeted_stratagem_cp_refund_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None

    bonus_clause = (
        r"(?:adding (?P<bonus>\d+) to the result if there (?:are|is) one or more friendly "
        r"(?P<bonus_keyword>[a-z0-9 ]+?) models? within (?P<bonus_range>\d+) )?"
    )
    direct_pattern = (
        r"(?:the bearer loses the smoke keyword but )?each time you target "
        r"(?:this unit|that unit|the bearer|the bearers unit|the bearer s unit|this models unit|this model s unit) "
        r"with a stratagem roll one d6 "
        + bonus_clause +
        r"on a (?P<roll>\d+) (?:you )?gain (?P<cp>\d+) ?cp"
    )
    select_pattern = (
        r"each time you select "
        r"(?:the bearers unit|the bearer s unit|this models unit|this model s unit|its unit|that unit|this unit) "
        r"as the target of a stratagem roll one d6 "
        + bonus_clause +
        r"on a (?P<roll>\d+) (?:you )?gain (?P<cp>\d+) ?cp"
    )
    smoke_loss = "bearer loses the smoke keyword" in norm
    for pattern in (direct_pattern, select_pattern):
        m = re.fullmatch(pattern, norm)
        if not m:
            continue
        roll = m.group("roll") or "5"
        cp = m.group("cp") or "1"
        bonus = m.group("bonus")
        bonus_keyword = re.sub(r"\s+", " ", str(m.group("bonus_keyword") or "").strip()).upper()
        bonus_range = m.group("bonus_range") or "0"
        bonus_note = ""
        if bonus:
            bonus_note = f", adding {bonus} if one or more friendly {bonus_keyword} models are within {bonus_range}\""
        if smoke_loss:
            return (
                "Supported",
                f"Bearer loses the SMOKE keyword; when targeted by a Stratagem, roll D6{bonus_note} and gain {cp} CP on {roll}+ (CP gain guardrail respected).",
            )
        return (
            "Supported",
            f"When targeted by a Stratagem, roll D6{bonus_note} and gain {cp} CP on {roll}+ (CP gain guardrail respected).",
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
        f"Opponent stratagems targeting units within {rng}\" have +1CP (non-cumulative; if affordable the increased cost must be paid, otherwise no CP are spent/effects do not resolve and that Stratagem still counts as used).",
    )


def _overwatch_hit_threshold_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"each time you target this unit with the fire overwatch stratagem "
        r"(?:while|when) resolving that stratagem hits are scored on unmodified hit rolls of (?P<threshold>\d)\+?",
        norm,
    )
    if not m:
        return None
    threshold = str(m.group("threshold") or "").strip()
    if threshold not in {"2", "3", "4", "5", "6"}:
        return None
    return ("Supported", f"Fire Overwatch with this unit scores hits on unmodified {threshold}+ while resolving the Stratagem.")


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
    crit_hit_match = re.search(
        r"a critical hit is scored on an unmodified hit roll of (\d)\+?(?: instead of only a 6)?",
        low,
        flags=re.IGNORECASE,
    )
    if crit_hit_match:
        notes.append(f"Leading: attacks score Critical Hits on unmodified {crit_hit_match.group(1)}+.")

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
        rf"{lead_prefix}(?:in addition )?each time a model in that unit makes an attack a critical hit is scored on an unmodified hit roll of \d\+?(?: instead of only a 6)?",
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
        r"(?: that targets (?:an?|the)?\s*(?:closest (?:eligible )?)?(?:enemy\s+)?(?:unit|target))?"
        r"[,;:]?\s*(?:you can\s*)?re-?roll (?:a|any)?\s*hit roll(?:s)? of 1$",
        re.IGNORECASE,
    )
    base_any_re = re.compile(
        r"^each time a model in this unit makes (?:a|an) attack(?:s)?"
        r"(?: that targets (?:an?|the)?\s*(?:closest (?:eligible )?)?(?:enemy\s+)?(?:unit|target))?"
        r"[,;:]?\s*(?:you can\s*)?re-?roll (?:a|any)?\s*hit roll(?:s)? of 1$",
        re.IGNORECASE,
    )
    objective_clause_re = re.compile(
        r"^if (?:that attack targets|the target of that attack is) (?:a unit )?(?:that is )?"
        r"within range of (?:an|one or more) objective marker(?:s)?"
        r"(?: you do not control| your opponent controls)?"
        r"\s*[,;:]?\s*(?:you can\s*)?re-?roll the hit roll instead$",
        re.IGNORECASE,
    )
    closest_clause_re = re.compile(
        r"^if (?:that attack targets|the target of that attack is) the closest (?:eligible )?(?:enemy )?(?:unit|target)"
        r"\s*[,;:]?\s*(?:you can\s*)?re-?roll the hit roll instead$",
        re.IGNORECASE,
    )
    charge_clause_re = re.compile(
        r"^if this unit made a charge move this turn"
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
    charge_sentences = [s for s in sentences if charge_clause_re.match(s.lower())]
    unsupported = [
        s
        for s in sentences
        if s not in base_sentences
        and not objective_clause_re.match(s.lower())
        and not closest_clause_re.match(s.lower())
        and not charge_clause_re.match(s.lower())
    ]

    if objective_sentences:
        notes.append("If the target is within range of an objective marker, the Hit roll can be re-rolled instead (optional).")
    if closest_sentences:
        notes.append("If the target is the closest eligible target, the Hit roll can be re-rolled instead (optional).")
    if charge_sentences:
        notes.append("If this unit made a Charge move this turn, the Hit roll can be re-rolled instead (optional).")

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
        r"^if (?:that attack targets|the target of that attack is|that enemy unit is) "
        r"(?:(?:a|an) (?:enemy )?unit )?(?:that is )?"
        r"within range of (?:an|one or more) objective marker(?:s)?"
        r"(?: you do not control| your opponent controls)?"
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
        r"(?:(?:that )?has (?P<max>\d+) or fewer models (?:and )?)?"
        r"(?:that is )?wholly within (?P<range>\d+) of this transport "
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


def _embarking_firing_deck_weight_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    all_models_pattern = (
        r"while embarked within a transport each model takes up the space of 2 models "
        r"and each weapon equipped by these models is considered to be 2 models weapons for the purposes of the firing deck ability"
    )
    heavy_weapons_gunner_pattern = (
        r"while embarked within a transport each heavy weapons gunner model takes up the space of 2 models "
        r"and each weapon equipped by these models is considered to be 2 models weapons for the purposes of the firing deck ability"
    )
    if re.fullmatch(all_models_pattern, norm):
        return (
            "Supported",
            "While embarked, each model counts as 2 transport slots and each selected weapon counts as 2 for Firing Deck limits.",
        )
    if re.fullmatch(heavy_weapons_gunner_pattern, norm):
        return (
            "Supported",
            "While embarked, each Heavy Weapons Gunner model counts as 2 transport slots and each selected Heavy Weapons Gunner weapon counts as 2 for Firing Deck limits.",
        )
    return None


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


def _post_deployment_redeploy_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"(?:if your army includes this model )?after both players have deployed their armies "
        r"select up to (?P<count>\d+|one|two|three|four|five|six|d3(?: \+ \d+)?) "
        r"(?P<filter>[a-z0-9 ']+?) units? from your army and redeploy them(?: (?P<tail>.*))?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    count = str(m.group("count") or "").strip().upper()
    if not count:
        count = "3"
    unit_filter = str(m.group("filter") or "").strip().upper()
    if not unit_filter:
        unit_filter = "friendly"
    tail = str(m.group("tail") or "").strip()
    note = f"After deployment: redeploy up to {count} {unit_filter} unit(s)."
    if "strategic reserves" in tail or "strategic reserves" in norm:
        note = f"{note} Selected units can be placed into Strategic Reserves regardless of normal limits."
    return ("Supported", note)


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
    base = (
        r"(?:once per battle(?:,)?\s+)?at the end of your opponents turn if this unit is not within engagement range of one or more enemy units "
        r"you can remove (?:it|this unit|that unit) from the battlefield"
    )
    strategic_reserves_pattern = rf"{base} and place (?:it|this unit|that unit) into strategic reserves"
    tunneling_pattern = (
        rf"{base} in the reinforcements step of your next movement phase set it up anywhere on the battlefield "
        r"that is more than (?P<dist>\d+) horizontally away from all enemy models"
    )
    if re.fullmatch(strategic_reserves_pattern, norm):
        note = "End of opponent's turn: if not in Engagement Range, may enter Strategic Reserves."
        if "once per battle" in norm:
            note = f"{note} Once per battle."
        return ("Supported", note)
    m = re.fullmatch(tunneling_pattern, norm)
    if not m:
        return None
    note = (
        "End of opponent's turn: if not in Engagement Range, remove the unit and set it up in your next Reinforcements "
        f"step more than {m.group('dist')}\" horizontally from enemy models."
    )
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
        r"in your shooting phase after this (?:model|unit) has shot select one enemy unit "
        r"(?:(?P<exclude>excluding monsters and vehicles) )?hit by one or more of those attacks "
        r"(?:made with (?:(?:a|an|the|its)\s+)?(?P<weapon>[a-z0-9 ]+) )?"
        r"(?:excluding monsters and vehicles )?until the start of your next turn that enemy unit is suppressed "
        r"while a unit is suppressed each time a model in that unit makes an attack subtract 1 from the hit roll"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    weapon = str(m.group("weapon") or "").strip()
    excluded_mv = bool(str(m.group("exclude") or "").strip()) or ("excluding monsters and vehicles" in norm)
    if excluded_mv:
        if weapon:
            return (
                "Supported",
                f"After shooting, suppress a hit enemy non-MONSTER/VEHICLE unit hit by {weapon} for -1 to hit until your next turn.",
            )
        return ("Supported", "After shooting, suppress a hit enemy unit (not MONSTER/VEHICLE) for -1 to hit until your next turn.")
    if weapon:
        return ("Supported", f"After shooting, suppress a hit enemy unit hit by {weapon} for -1 to hit until your next turn.")
    return ("Supported", "After shooting, suppress a hit enemy unit for -1 to hit until your next turn.")


def _post_shoot_reactive_move_no_charge_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase after this (?:model s unit|models unit|unit) has shot"
        r"(?: if it is not within engagement range of (?:one or more|any) enemy units)? "
        r"(?:it|that unit|this unit) can make a normal move of up to (?P<move>d6|\d+)"
        r"(?: as if it were your movement phase)? "
        r"if it does until the end of the turn (?:that unit|this unit) is not eligible to declare a charge"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    move = str(m.group("move") or "").strip().upper()
    move_label = "D6" if move == "D6" else move
    gated = "if it is not within engagement range" in norm
    note = f"After shooting: this unit can make a Normal move of up to {move_label}\" and then cannot charge this turn."
    if gated:
        note = f"After shooting (if not in Engagement Range): this unit can make a Normal move of up to {move_label}\" and then cannot charge this turn."
    return ("Supported", note)


def _post_shoot_no_cover_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase (?:(?:each time )?this (?P<sel_subject>model|unit) is selected to shoot )?"
        r"after (?:this (?P<subject>model|unit) has shot|resolving (?:its|those) attacks) select one enemy unit "
        r"(?:that was )?hit by one or more of those attacks "
        r"(?:made with (?:a|an|the|its) (?P<weapon>[a-z0-9 ]+) )?"
        r"until the (?P<duration>end of the phase|start of your next shooting phase) "
        r"that (?:enemy )?unit cannot have the benefit of cover"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    weapon = str(m.group("weapon") or "").strip()
    duration = str(m.group("duration") or "").strip().lower()
    if "start of your next shooting phase" in duration:
        if weapon:
            return (
                "Supported",
                f"After shooting: select a hit enemy unit hit by {weapon}; it cannot gain Benefit of Cover until your next Shooting phase.",
            )
        return (
            "Supported",
            "After shooting: select a hit enemy unit; it cannot gain Benefit of Cover until your next Shooting phase.",
        )
    if weapon:
        return ("Supported", f"After shooting: select a hit enemy unit hit by {weapon}; it cannot gain Benefit of Cover until phase end.")
    return ("Supported", "After shooting: select a hit enemy unit; it cannot gain Benefit of Cover until phase end.")


def _post_shoot_disembark_wound_reroll_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase after this model has shot select one enemy unit "
        r"(?:(?:that was )?hit by one or more of those attacks|it scored one or more hits against this phase) "
        r"until the end of the phase each time a friendly model that disembarked from this transport this turn makes an attack "
        r"that targets that enemy unit you can reroll the wound roll"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "After shooting: select a hit enemy unit; friendly models disembarked from this TRANSPORT this turn re-roll Wound rolls against it until phase end.",
    )


def _post_shoot_afflicted_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase (?:each time this (?:model|unit) is selected to shoot )?after this (?:model|unit) has shot "
        r"select one enemy unit hit by one or more of those attacks until the start of your next turn that enemy unit is afflicted"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "Post-shoot selection: choose a hit enemy unit; it is marked Afflicted until the start of your next turn.",
    )


def _post_shoot_ap_bonus_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"in your shooting phase after this (?:model|unit) has shot select one enemy unit "
        r"(?:excluding monsters and vehicles )?hit by one or more of those attacks "
        r"until the end of the phase each time a friendly (?P<keyword>[a-z0-9 ]+?) unit makes (?:a|an) "
        r"(?:(?P<atype>ranged|melee) )?attack that targets that enemy unit improve the armour penetration characteristic "
        r"of that attack by (?P<val>\d+)(?: the same enemy unit can only be affected by this ability once per (?:turn|phase)"
        r"| each unit can only be selected for this ability once per turn)?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    keyword = str(m.group("keyword") or "").strip().upper()
    atype = str(m.group("atype") or "").strip().lower()
    try:
        val = int(m.group("val") or 0)
    except Exception:
        val = 0
    if val <= 0:
        return None
    scope = "attacks"
    if atype == "ranged":
        scope = "ranged attacks"
    elif atype == "melee":
        scope = "melee attacks"
    note = f"After shooting: select a hit enemy unit; friendly {keyword} {scope} against it gain AP +{val} until phase end."
    if "excluding monsters and vehicles" in norm:
        note = f"After shooting: select a hit enemy unit (not MONSTER/VEHICLE); friendly {keyword} {scope} against it gain AP +{val} until phase end."
    if "once per turn" in norm:
        note += " Target limit: once per turn."
    elif "once per phase" in norm:
        note += " Target limit: once per phase."
    return ("Supported", note)


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
        "After shooting, pick a hit enemy unit; until your next Shooting phase, it suffers -1 to Battle-shock/Leadership tests (stacking with repeated applications).",
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
    engaged_pattern = (
        r"at the end of the fight phase you can select one enemy unit within engagement range of this model "
        r"and roll (?:eight|8) d6 for each 4 that enemy unit suffers 1 mortal wounds?"
    )
    if re.fullmatch(engaged_pattern, norm):
        return ("Supported", "End of Fight phase: pick an engaged enemy; roll 8D6, each 4+ inflicts 1 mortal wound.")

    aura_threshold_pattern = (
        r"at the end of the fight phase roll (?:one|1) d6 for each enemy unit within (?P<range>\d+) of this model "
        r"on a (?P<threshold>\d) that enemy unit suffers (?P<mw>d3|d6|\d+) mortal wounds?"
    )
    m = re.fullmatch(aura_threshold_pattern, norm)
    if not m:
        return None
    range_val = str(m.group("range") or "").strip()
    threshold = str(m.group("threshold") or "").strip()
    mortal = str(m.group("mw") or "").strip().upper()
    if not range_val.isdigit() or not threshold.isdigit() or not mortal:
        return None
    return (
        "Supported",
        f'End of Fight phase: roll D6 for each enemy within {range_val}"; on {threshold}+ it suffers {mortal} mortal wounds.',
    )


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


def _command_phase_end_enemy_within_range_mortal_table_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once per battle at the end of your command phase this model can use this ability "
        r"if it does roll (?:one|1) d6 for each enemy unit within (?P<range>\d+) of this model "
        r"on a 2 5 that enemy unit suffers d3 mortal wounds? "
        r"on a 6 that enemy unit suffers d3 3 mortal wounds?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    range_val = m.group("range") or "12"
    return (
        "Supported",
        f"Once per battle (end of Command phase): roll D6 for each enemy within {range_val}\"; 2-5=D3 mortal wounds, 6=D3+3 mortal wounds.",
    )


def _reanimation_dice_reroll_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time this units reanimation protocols activate you can reroll the dice to see how many wounds are reanimated"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "Each Reanimation Protocols activation: re-roll the wounds-reanimated dice (auto-applied when strictly better).",
    )


def _reanimation_additional_d3_aura_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"while a friendly necrons unit is within (?P<range>\d+) of this model each time that units reanimation protocols activate "
        r"that unit reanimates an additional d3 wounds?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    range_val = m.group("range") or "3"
    return (
        "Supported",
        f"Reanimation aura: friendly NECRONS within {range_val}\" gain one additional D3 reanimated wounds per activation.",
    )


def _reanimation_additional_one_once_per_battle_round_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once per battle round when a friendly necrons unit within (?P<range>\d+) of the bearer activates its reanimation protocols "
        r"the bearer can use this ability if it does that unit reanimates (?P<bonus>\d+) additional wounds?"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    range_val = m.group("range") or "3"
    bonus = m.group("bonus") or "1"
    return (
        "Supported",
        f"Once per battle round on nearby Reanimation Protocols activation: add +{bonus} reanimated wound within {range_val}\".",
    )


def _repair_barge_reanimation_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once per turn just after an enemy unit finishes making its attacks if one or more friendly necron warriors units within "
        r"(?P<range>\d+) of this model lost one or more wounds as a result of those attacks this model can use this ability if it does "
        r"select one of those necron warriors units that units reanimation protocols activate the same necron warriors unit cannot be "
        r"selected for this ability more than once per turn"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    range_val = m.group("range") or "3"
    return (
        "Supported",
        f"Post-attack reactive selection: friendly NECRON WARRIORS within {range_val}\" can trigger Reanimation Protocols (D3), once per source model per turn and each target once per turn.",
    )


def _start_any_phase_unit_invuln_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"once per battle at the start of any phase this model can use this ability if it does until the end of the phase "
        r"all models in this model(?: s|s) unit have a (?P<val>[1-6]) invulnerable save"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    return (
        "Supported",
        f"Once per battle (start of any phase): models in this model's unit gain a {m.group('val')}+ invulnerable save until end of phase.",
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
        r"(?:each time |if )?(?:(?:an? )?[a-z0-9 ]+ model in this unit|a model in this unit|this model) "
        r"is destroyed by a melee attack if (?:that model|it) has not fought this phase "
        r"roll one d6 on a (?P<threshold>\d+) do not remove (?:it|this model|that destroyed model) from play "
        r"(?:that destroyed model|the destroyed model|this model) can fight after the attacking (?:unit|model s unit|models unit) has finished making its attacks "
        r"and (?:is|it is) then removed from play"
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


def _advance_no_roll_with_phase_move_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None

    advance_pattern = (
        r"each time (?:this unit|this model|this models unit|this model s unit|the bearer s unit|that unit) advances "
        r"do not make an advance roll(?: for it)? "
        r"instead until the end of the phase add (?P<dist>\d+) to the move characteristic "
        r"(?:of (?:models in )?)?(?:this unit|this model|this models unit|this model s unit|the bearer s unit|that unit)"
    )
    advance_match = re.search(advance_pattern, norm)
    if not advance_match:
        return None
    try:
        dist = int(advance_match.group("dist") or 0)
    except Exception:
        dist = 0
    if dist <= 0:
        return None

    phase_move_pattern = (
        r"each time a model in (?:the bearer s|that|this|this model s|this models) unit makes a "
        r"(?P<moves>.+?) move(?: until that move is finished)? "
        r"it can move horizontally through models and terrain features"
    )
    phase_move_match = re.search(phase_move_pattern, norm)
    if not phase_move_match:
        return None
    moves_text = str(phase_move_match.group("moves") or "")
    if "normal" not in moves_text or "advance" not in moves_text or "fall back" not in moves_text:
        return None

    return (
        "Supported",
        f"Advance: fixed +{dist}\" Move instead of rolling. Normal/Advance/Fall Back: move horizontally through models and terrain; cannot end overlapping models.",
    )


def _advance_no_roll_fixed_distance_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"(?:[a-z0-9 ]+ model only )?"
        r"(?:while this model is leading a unit )?"
        r"each time (?:this unit|this model|this models unit|this model s unit|the bearer s unit|that unit) advances "
        r"do not make an advance roll(?: for it)? "
        r"instead until the end of the phase add (?P<dist>\d+) to the move characteristic "
        r"(?:of (?:models in )?)?(?:this unit|this model|this models unit|this model s unit|the bearer s unit|that unit)"
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


def _charge_move_model_weapon_profile_attacks_bonus_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time this model makes a charge move until the end of the turn add (?P<strike>\d+) "
        r"to the attacks characteristic of (?:this model s|this models|its) (?P<weapon1>[a-z0-9 ]+?) strike profile "
        r"and add (?P<sweep>\d+) to the attacks characteristic of (?:this model s|this models|its) "
        r"(?P<weapon2>[a-z0-9 ]+?) sweep profile"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    try:
        strike_bonus = int(m.group("strike") or 0)
    except Exception:
        strike_bonus = 0
    try:
        sweep_bonus = int(m.group("sweep") or 0)
    except Exception:
        sweep_bonus = 0
    if strike_bonus <= 0 and sweep_bonus <= 0:
        return None
    weapon1 = str(m.group("weapon1") or "").strip()
    weapon2 = str(m.group("weapon2") or "").strip()
    weapon = weapon1 or weapon2 or "weapon"
    return (
        "Supported",
        f"On charge: this model gains +{strike_bonus} Attacks on {weapon} strike profile and +{sweep_bonus} on {weapon} sweep profile until end of turn.",
    )


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


def _floating_death_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    required_phrases = (
        "each time this unit or an enemy unit ends a move",
        "for each model in this unit that is within 3 of one or more enemy units",
        "that model in this unit is destroyed then roll one d6",
        "on a 2 5",
        "on a 6",
        "mortal wound",
    )
    if not all(phrase in norm for phrase in required_phrases):
        return None
    if (
        "on a 2 5 that enemy unit suffers 1 mortal wound" in norm
        and "on a 6 that enemy unit suffers d3 mortal wounds" in norm
    ):
        return (
            "Supported",
            "Move end (self or enemy): each model within 3\" selects an enemy unit within 3\", is destroyed, then deals 1 mortal wound on 2-5 or D3 on 6.",
        )
    if (
        "on a 2 5 that enemy unit suffers d3 mortal wounds" in norm
        and "on a 6 that enemy unit suffers d6 mortal wounds" in norm
    ):
        return (
            "Supported",
            "Move end (self or enemy): each model within 3\" selects an enemy unit within 3\", is destroyed, then deals D3 mortal wounds on 2-5 or D6 on 6.",
        )
    return None


def _hazardous_test_modifier_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"each time (?:the bearer|this model|a model in this unit) takes a hazardous test "
        r"for this weapon profile subtract (?P<mod>\d+) from the result"
    )
    m = re.fullmatch(pattern, norm)
    if not m:
        return None
    try:
        mod = int(m.group("mod") or 0)
    except Exception:
        mod = 0
    if mod <= 0:
        return None
    fail_max = min(6, 1 + mod)
    return (
        "Supported",
        f"Hazardous tests for this profile use a -{mod} modifier (raw failures on 1-{fail_max}).",
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
        return ("Supported", "Shoot after Falling Back; when doing so only models equipped with this wargear can make ranged attacks.")
    if "loses the smoke keyword" in norm:
        return ("Supported", "Shoot after Falling Back; while doing so the unit loses the SMOKE keyword.")
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


def _order_range_extension_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"each time (?:this model|the officer in the bearers unit) issues an order "
        r"it can issue (?:it|that order) to an eligible unit up to (?P<rng>\d+) away",
        norm,
    )
    if not m:
        return None
    rng = m.group("rng") or "0"
    return (
        "Supported",
        f"Voice of Command range extension: issuing OFFICER can target eligible units up to {rng}\" away.",
    )


def _act_of_faith_cherub_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    m = re.fullmatch(
        r"(?P<count>once|twice) per battle after this unit has performed an act of faith "
        r"you gain 1 miracle dice(?: designers note .+)?",
        norm,
    )
    if not m:
        return None
    count = str(m.group("count") or "").strip().lower()
    uses = 2 if count == "twice" else 1
    label = "Twice per battle" if uses == 2 else "Once per battle"
    return (
        "Supported",
        f"After this unit performs an Act of Faith: gain 1 Miracle die ({label.lower()}).",
    )


def _ammo_runt_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    if "ammo runt" not in norm:
        return None
    m = re.fullmatch(
        r"once per battle(?P<per> for each ammo runt this unit has)? when this unit is selected to shoot "
        r"it can use this ability if it does until the end of the phase ranged weapons equipped by models in this unit "
        r"have the lethal hits ability(?: designers note .+)?",
        norm,
    )
    if not m:
        return None
    if bool(m.group("per")):
        return (
            "Supported",
            "Ammo Runt: when selected to shoot, unit ranged weapons gain Lethal Hits; uses are tracked per Ammo Runt.",
        )
    return (
        "Supported",
        "Ammo Runt: once per battle when selected to shoot, unit ranged weapons gain Lethal Hits until end of phase.",
    )


def _bomb_squigs_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    if "bomb squig" not in norm:
        return None
    m = re.fullmatch(
        r"once per battle for each bomb squig this unit has after this unit ends a normal move "
        r"you can use one bomb squig if you do select one enemy unit within (?P<range>\d+) and visible to this unit "
        r"and roll one d6 on a (?P<threshold>\d)\+? that enemy unit suffers d3 mortal wounds(?: designers note .+)?",
        norm,
    )
    if not m:
        return None
    if "place two bomb squig tokens next to the unit" in norm:
        return (
            "Supported",
            "Bomb Squigs: after a Normal move, optional 12\" visible target roll (3+ => D3 mortal wounds); two uses tracked.",
        )
    if "place a bomb squig token next to the unit" in norm:
        return (
            "Supported",
            "Bomb Squigs: after a Normal move, optional 12\" visible target roll (3+ => D3 mortal wounds); one use tracked.",
        )
    if "place the relevant number of bomb squig tokens next to the unit" in norm:
        return (
            "Supported",
            "Bomb Squigs: after a Normal move, optional 12\" visible target roll (3+ => D3 mortal wounds); uses tracked per Bomb Squig.",
        )
    return (
        "Supported",
        "Bomb Squigs: after a Normal move, optional 12\" visible target roll (3+ => D3 mortal wounds) with tracked uses.",
    )


def _attached_unit_support(name: str, description: str) -> Optional[Tuple[str, str]]:
    if _norm(name) != "attached unit":
        return None
    note = "Attached Unit section parsed to extend leader attachment eligibility."
    text = _norm_rules_text(_strip_html(description))
    if re.search(
        r"if a .+\s+(?:(?:model|unit)\s+)?from your army is attached to this unit during the declare battle formations step"
        r"\s*that model gains(?: the)? scouts? \d+",
        text,
    ):
        m = re.search(r"scouts? (?P<rng>\d+)", text)
        rng = m.group("rng") if m else "6"
        return ("Supported", f"{note} Matching attached Leaders gain Scouts {rng}\" at battle formations.")
    if " gains " in text:
        return ("Partial", f"{note} Additional leader-gain effects not implemented.")
    return ("Supported", note)


def _enhancement_support(name: str, enh_id: str, description: str) -> Tuple[str, str]:
    explicit = {
        "000008432002": "Berzerker Glaive: +1A/+1D to bearer melee weapons (excluding Extra Attacks).",
        "000008432003": "Helm of Brazen Ire: reduce damage by 1 (min 1).",
        "000008432004": "Favoured of Khorne: Blessings rerolls while bearer on battlefield.",
        "000008432005": "Battle-lust: re-roll Charge; +1 Charge with Unbridled Bloodlust.",
        "000008470002": "Saintly Example: when the bearer is destroyed, gain D3 additional Miracle dice.",
        "000008470003": "Through Suffering, Strength: bearer melee weapons gain +1 Attacks/Strength/Damage, or +2 instead while the bearer has lost one or more wounds.",
        "000008470004": "Chaplet of Sacrifice: end of your Command phase, bearer can re-roll 1 Miracle die from your pool (up to 3 if the bearer's unit is below Starting Strength).",
        "000008470005": "Mantle of Ophelia: each time an attack is allocated to the bearer, that attack's Damage characteristic is changed to 1.",
        "000009067002": "Prowling Agitant: once per turn, after an enemy Normal/Advance/Fall Back move ends within 9\" of the bearer’s unit (and while not engaged), that unit can make a reactive Normal move up to D6\".",
        "000009067003": "A Chink in Their Armour: when the bearer is set up as Reinforcements, ranged weapons in the bearer’s unit gain [LETHAL HITS] until the end of your next Fight phase.",
        "000009067004": "Our Time Is Nigh: once per battle, when the bearer’s unit declares a charge, optional yes/no activation grants +2 to that unit’s Charge rolls until end of phase.",
        "000009067005": "Assassination Edict: attacks made by models in the bearer’s unit gain +1 to hit when targeting CHARACTER units.",
        "000009899002": "Phoenix Gem: return on 2+ at end of phase after first destruction.",
        "000009899003": "Timeless Strategist: +1 Battle Focus token if bearer on battlefield.",
        "000009899004": "Gift of Foresight: Command Re-roll for 0CP once per battle round.",
        "000009899005": "Psychic Destroyer: +1 Damage to bearer ranged Psychic weapons.",
        "000009903002": "Firstdrawn Blade: models in the bearer's unit gain Scouts 9\" via enhancement scout-distance hook.",
        "000009903003": "Mirage Field: attacks targeting the bearer's unit suffer -1 to hit (bearer-unit target hit-penalty parsing).",
        "000009903004": "Seersight Strike: Psychic weapons equipped by the bearer gain [ANTI-MONSTER 2+] and [ANTI-VEHICLE 2+].",
        "000009903005": "Echoes of Ulthanesh: in your Command phase roll D6 (+1 outside own deployment zone, +1 additional in opponent deployment zone); on 5+ gain 1CP.",
        "000009907002": "Light of Clarity: in your Command phase, select one friendly WRAITH CONSTRUCT unit within 12\" of the bearer; until your next Command phase, models in that unit gain +1 Objective Control if INFANTRY or +3 Objective Control if MONSTER.",
        "000009907003": "Stave of Kurnous: in your Command phase, select one friendly non-TITANIC WRAITH CONSTRUCT unit within 12\" of the bearer; until your next Command phase, attacks made by models in that unit gain [PRECISION] on Critical Wounds.",
        "000009907004": "Rune of Mists: in your Command phase, select one friendly WRAITH CONSTRUCT unit within 12\" of the bearer; until your next Command phase, ranged attacks targeting that unit grant it Benefit of Cover unless the attacker is within 18\".",
        "000009907005": "Higher Duty: once per turn, when an enemy unit ends a Normal/Advance/Fall Back move within 9\" of the bearer's unit, that unit can make a reactive Normal move up to 6\".",
        "000009915002": "Cegorach's Coil: after the bearer's unit ends a Charge move, select an engaged enemy and roll one D6 per bearer-unit model within Engagement Range of that enemy; each 4+ inflicts 1 mortal wound (max 6).",
        "000009915003": "Mask of Secrets: enemy non-MONSTER/non-VEHICLE units within Engagement Range of the bearer's unit that Fall Back must take Desperate Escape tests; if that enemy unit is Battle-shocked, those tests are at -1.",
        "000009915004": "Murder's Jest: bearer attacks that target units below Half-strength treat each successful Hit roll as a Critical Hit.",
        "000009915005": "Mistweave: while the bearer is leading, models in that attached unit gain Infiltrators.",
        "000009919002": "Gaze of Ynnead: the bearer's Eldritch Storm weapon gains [DEVASTATING WOUNDS].",
        "000009919003": "Storm of Whispers: in your Shooting phase, after the bearer has shot, select one enemy unit hit by one or more of those attacks; that unit must take a Battle-shock test.",
        "000009919004": "Borrowed Vigour: add 2 to the Attacks characteristic of the bearer's melee weapons.",
        "000009919005": "Morbid Might: each time the bearer makes a melee attack, you can re-roll the Wound roll.",
        "000010649002": "Key of Ghosts: models in the bearer's unit gain Scouts 6\".",
        "000010649003": "Weavers' Wail: add 3 to Strength and 1 to Attacks for the bearer's melee weapons.",
        "000010649004": "Fanged Leer: when using the bearer's Cruel Amusement ability, that model can select two shrieker cannon ability options instead of one.",
        "000010649005": "Shedskin Raiment: after deployment, redeploy up to three friendly HARLEQUINS units; selected units may be placed into Strategic Reserves regardless of limits.",
        "000010699002": "Pirate Prince: while Prince Yriel is leading, each spent Battle Focus token for that unit rolls D6 and refunds 1 token on 3+.",
        "000010699003": "Alacritous Assault: melee weapons equipped by models in the bearer's unit gain [LANCE].",
        "000010699004": "Exotic Munitions: ranged weapons equipped by models in the bearer's unit gain [ANTI-MONSTER 5+] and [ANTI-VEHICLE 5+].",
        "000010699005": "Adrenal Infusions: bearer unit can perform Fade Back without spending a Battle Focus token, ignores same-phase Fade Back cap, and does not consume that cap.",
        "000010193002": "Lord of Forbidden Lore: while bearer manifests a Ritual, add 6\" to that Ritual's range.",
        "000010193003": "Incandaeum: once per battle, bearer can select Doombolt even if that Ritual was already attempted this phase.",
        "000010193004": "Umbralefic Crystal: once per battle in Command phase, bearer unit can enter Strategic Reserves if not engaged; in Reinforcements this turn, it returns via Deep Strike placement (>9\" horizontally from enemies).",
        "000010193005": "Eldritch Vortex of E'taph: bearer Psychic weapons gain +1 Strength and +1 Damage.",
        "000010205002": "Risen Rubricae: at the start of Declare Battle Formations, select either two friendly RUBRICAE BATTLELINE units or one other friendly RUBRICAE unit; selected unit models gain Infiltrators (including attached CHARACTER models per FAQ).",
        "000010205003": "Arcane Thralls (Aura): friendly RUBRICAE units within 9\" of the bearer can re-roll Battle-shock tests.",
        "000010205004": "Lord of the Rubricae: while bearer is leading a unit, RUBRICAE models in that unit gain +1 to Hit rolls.",
        "000010205005": "The Stave Abominus: bearer's melee weapons gain [SUSTAINED HITS D3] and [DEVASTATING WOUNDS].",
        "000009923002": "Lucid Eye: in your Command phase, optional single-dialog Fate pool selection changes one Fate die by +1 or -1 (bounded to 1-6).",
        "000009923003": "Runes of Warding: models in the bearer's unit gain Feel No Pain 4+ against mortal wounds, Psychic attacks, and Devastating Wounds attacks caused by critical wounds.",
        "000009923004": "Stone of Eldritch Fury: +12\" range to the bearer's ranged Psychic weapons only.",
        "000009923005": "Torc of Morai-Heg: once per turn, opponent Stratagems targeting units within 12\" of the bearer cost +1CP.",
        "000009769002": "Guiding Presence: start of Shooting phase select friendly AELDARI VEHICLE within 9\" to gain +1 to hit until end of phase.",
        "000009769003": "Harmonisation Matrix: Command phase roll D6 if bearer/transport is within a controlled objective; on 3+, gain 1 CP.",
        "000009769004": "Spirit Stone of Raelyth: Lone Operative within 3\" of friendly AELDARI VEHICLE; Command phase select friendly AELDARI VEHICLE within 3\" to regain up to D3 lost wounds.",
        "000009769005": "Guileful Strategist: after deployment select up to three AELDARI VEHICLE units to redeploy; may place them into Strategic Reserves regardless of limits.",
        "000009911002": "Craftworld's Champion: bearer Objective Control is set to 5.",
        "000009911003": "Ethereal Pathway: at the start of Deploy Armies, optional single CHOOSE_QUARRY selection grants Infiltrators to up to two friendly Guardians units.",
        "000009911004": "Protector of the Paths: while leading Dire Avengers/Guardians, Fire Overwatch can be used for 0CP once per battle round; Overwatch hits on 5+ (or 4+ while within a controlled objective).",
        "000009911005": "Breath of Vaul: while leading Storm Guardians, flamer attack-count rolls and fusion-gun damage rolls can be re-rolled.",
        "000010704002": "Infamy (Aura): while enemy units are within 3\" of the bearer unit, models in those units suffer -1 Objective Control (minimum 1).",
        "000010704003": "Webway Pathstone: models in the bearer unit gain Deep Strike; once per battle at the end of your opponent's turn (if not in Engagement Range) the unit can enter Strategic Reserves via optional confirmation.",
        "000010704004": "Archraider: selected bearer CHARACTER model projects Lord of Deceit (Aura), increasing Stratagem CP cost by 1 for enemy targets within 12\".",
        "000010704005": "Voidstone: models in the bearer unit gain a 5+ invulnerable save.",
        "000009927002": "Aspect of Murder: bearer melee weapons gain +1 Damage and [Precision].",
        "000009927003": "Mantle of Wisdom: while leading Aspect Warriors, unit gains both Path of the Warrior abilities when selected to shoot or fight.",
        "000009927004": "Shimmerstone: while leading Aspect Warriors, ranged attacks targeting the unit suffer -1 to wound.",
        "000009927005": "Strategic Savant: while leading Aspect Warriors, models in the unit gain +1 Objective Control.",
        "000008348002": "Alien Cunning: after deployment, redeploy up to three friendly TYRANIDS units; selected units may be placed into Strategic Reserves regardless of limits.",
        "000008348003": "Perfectly Adapted: once per turn, bearer can re-roll one of Hit/Wound/Damage/Advance/Charge/Save (single shared use across those roll types).",
        "000008348004": "Synaptic Linchpin: while a friendly TYRANIDS unit is within 9\" of the bearer, it counts as within Synapse Range of your army.",
        "000008348005": "Adaptive Biology: bearer gains Feel No Pain 5+; at the start of any turn, if below starting wounds, upgrade to Feel No Pain 4+ for the rest of the battle.",
        "000010002002": "Faultless Opportunist: Heroic Intervention for 0CP even if another unit was targeted this phase.",
        "000010002005": "Rise to the Challenge: end of Fight phase (once per battle) fight one additional time and choose an Exquisite Swordsmanship ability.",
        "000010014002": "Pledge of Eternal Servitude: first time bearer is destroyed, takes a Leadership test at phase end; on pass, bearer returns with D6 wounds.",
        "000010014003": "Pledge of Dark Glory: while bearer is leading a unit, models in that unit improve Leadership by 1 and Objective Control by 1.",
        "000010014004": "Pledge of Mortal Pain: start of Shooting phase, select visible enemy within 12\" of bearer; it takes a Leadership test (subtract 2 from result if Battle-shocked) and suffers 3 mortal wounds on failure.",
        "000010014005": "Pledge of Unholy Fortune: once per turn after a hit, wound or saving throw for bearer’s unit, if bearer is not Battle-shocked, treat that roll as an unmodified 6.",
        "000010010002": "Empyric Suffusion: once per battle round, one friendly SLAANESH unit within 6\" of the bearer can be targeted with Heroic Intervention for 0CP.",
        "000010010003": "Dark Blessings: once per battle, after an enemy selects targets, the bearer can gain a 3+ invulnerable save until end of phase.",
        "000010010004": "Possessed Blade: start of battle select one bearer melee weapon for +1 Attacks; each time bearer is selected to fight, optional +1 Damage and selected weapon gains [DEVASTATING WOUNDS] and [HAZARDOUS] for those attacks.",
        "000010010005": "Warp Walker: bearer unit Advances with fixed +6\" (no Advance roll); on Normal/Advance/Fall Back, models can move through enemy models, can move within Engagement Range but cannot end there, and Fall Back Desperate Escape tests are automatically passed.",
        "000010006002": "Sublime Prescience: once per turn in your Movement phase, select a friendly Emperor's Children Transport in Strategic Reserves; until end of phase it treats the battle round as one higher for setup.",
        "000010006003": "Spearhead Striker: each time bearer unit disembarks, until end of turn it can re-roll Charge rolls and enemy units cannot use Fire Overwatch against it.",
        "000010006004": "Accomplished Tactician: once per turn in opponent's Shooting phase after an enemy unit shoots, select a hit friendly Emperor's Children unit within 9\" of bearer and a friendly Transport it is wholly within 6\" of and can embark in; that unit embarks.",
        "000010006005": "Heretek Adept: once per battle round, when a saving throw is failed for a friendly Emperor's Children Vehicle model within 6\" of bearer, set that attack's Damage to 0.",
        "000010018002": "Eager to Prove: bearer unit can re-roll Charge rolls; while bearer unit is Favoured Champions, models in that unit gain +2\" Move.",
        "000010018003": "Repulsed by Weakness: enemy units (excluding MONSTERS/VEHICLES) within Engagement Range of bearer unit must take Desperate Escape tests when they Fall Back; if bearer unit is Favoured Champions, subtract 1 from those tests.",
        "000010018004": "Proud and Vainglorious: bearer unit can re-roll Battle-shock and Leadership tests; while bearer unit is Favoured Champions, models in that unit gain +1 Objective Control.",
        "000010018005": "Slayer of Champions: bearer melee weapons gain [PRECISION]; bearer melee attacks that target CHARACTER units improve Strength and AP by 1.",
        "000009998002": "Steeped in Suffering: bearer unit gains +1 to hit vs targets below Starting Strength and +1 to wound vs targets below Half-strength.",
        "000009998003": "Intoxicating Musk: melee attacks targeting the bearer's unit suffer -1 to wound when attack Strength exceeds that unit's Toughness.",
        "000009998004": "Tactical Perfection: after deployment, redeploy up to two friendly EMPEROR'S CHILDREN units; selected units may be placed into Strategic Reserves regardless of limits.",
        "000009998005": "Loathsome Dexterity: on Normal/Advance/Fall Back, bearer unit models can move through enemy models, can move within Engagement Range but cannot end there, and Fall Back Desperate Escape tests are automatically passed.",
        "000010654002": "Tears of the Phoenix: models in the bearer's unit can ignore any or all modifiers to melee Weapon Skill, Hit roll, and Wound roll (per-attack deterministic modifier-choice support).",
        "000010654003": "Exalted Patron: bearer gains +1\" Move and can attach to Flawless Blades during Declare Battle Formations.",
        "000010654004": "Soulstain Made Manifest: start of Fight phase optional single-dialog target selection (with None) for one engaged enemy to take a Battle-shock test at -1.",
        "000010654005": "Spiritsliver: bearer melee weapons gain +1 Strength and +1 Attacks.",
        "000008412002": "Regenerating Monstrosity: while resolving Feed the Swarm, the bearer's unit can be regenerated up to twice per phase instead of once.",
        "000008412004": "Biophagic Flow (Aura): while a friendly Harvester model is within 12\" of the bearer, that Harvester's Feed the Swarm regeneration range is 9\" instead of 6\".",
        "000010078002": "Icon of War: BLOOD LEGIONS within 6\" gain Blessings of Khorne; with Might of Khorne active, may re-roll Battle-shock tests.",
        "000010078003": "Blood-forged Armour: set bearer Save to 2+; gain 1 Blood Tithe point when bearer is destroyed.",
        "000010078004": "Disciple of Khorne: Lord on Juggernaut can attach to Bloodcrushers/Flesh Hounds; bearer gains Deep Strike and BLOOD LEGIONS (instead of WORLD EATERS) while leading; attached unit benefits from Blessings of Khorne (FAQ).",
        "000010078005": "Blade of Endless Bloodshed: +1 A/S/D for bearer melee weapons; melee kill auto-grants 1 Blood Tithe point.",
        "000010086002": "Murderous Onslaught: if bearer unit disembarked this turn, enemy units cannot use Fire Overwatch against it until end of turn.",
        "000010086003": "Aggressive Deployment: if bearer starts embarked in a Dedicated Transport, that Transport gains Scouts 9\".",
        "000010086004": "Unleash Hell: start of Shooting phase select a friendly Vehicle within 6\" (or bearer’s Transport); after it shoots, suppress a hit enemy unit until your next turn.",
        "000010086005": "Infernal Infusion: once per battle at the start of the Fight phase, bearer unit gains Fights First until end of phase.",
        "000010074002": "Chosen of the Blood God: add 3\" to the range of the bearer’s Aura abilities.",
        "000010074003": "Butcher Lord: bearer can attach to Jakhals or Goremongers during Declare Battle Formations; while attached to GOREMONGERS, bearer has Infiltrators.",
        "000010074004": "Brazen Form: bearer gains +1 Toughness and Feel No Pain 5+.",
        "000010074005": "Strategic Slaughter: after deployment, redeploy up to three friendly Jakhals and/or Goremongers units; selected units may be placed into Strategic Reserves regardless of limits.",
        "000010082002": "Malicious Vigour: bearer unit treats each Brazen Fury move roll as a 6 for distance.",
        "000010082003": "Killing Clarity: each time bearer unit destroys an enemy unit, roll D6 and gain 1CP on 4+.",
        "000010082004": "Frenzied Focus: attacks made by models in bearer unit score critical hits on unmodified 5+.",
        "000010082005": "Violent Demise: bearer Deadly Demise triggers on 2+ and uses Deadly Demise D3+1 instead of D3.",
        "000009847002": "Archslaughterer: bearer melee weapons gain +1 AP; while bearer has VESSEL OF WRATH, bearer melee weapons gain +1 Damage.",
        "000009847003": "Vox-diabolus: each melee kill by the bearer’s unit rolls D6 (+1 if bearer is VESSEL OF WRATH) and gains 1CP on 4+.",
        "000009847004": "Avenger's Crown: if the bearer is destroyed by a melee attack and has not fought this phase, roll D6; on 2+ that model fights after the attacker finishes, then is removed.",
        "000009847005": "Gateways to Glory: on Normal/Advance/Charge moves, bearer can move through models/terrain; Normal/Advance moves cannot end in Engagement Range.",
        "000010435002": "Oathbound Speculator: bearer’s unit re-rolls Wound rolls of 1; when selected to shoot or fight, optional spend 3YP for +1 to wound until end of phase.",
        "000010435003": "Dead Reckoning: at end of turn, if bearer is on battlefield and no YP were spent in that turn, optional gain 1YP.",
        "000010435004": "Iron Ambassador: once per battle when bearer’s unit is selected to shoot, optional spend up to 3YP; bearer’s ranged weapons gain +Damage equal to YP spent until end of phase.",
        "000010435005": "Ancestral Crest: once per turn, when bearer’s unit is targeted by Command Re-roll, optional spend 1YP to reduce that CP cost by 1.",
        "000009823002": "Bastion Shield: ranged attacks against bearer’s unit worsen AP by 1 within 12\"; optional spend 1YP extends the AP worsening range to 18\" until end of phase.",
        "000009823003": "Quake Multigenerator: after bearer shoots, select a non-TITANIC enemy unit hit by bearer attacks; that unit is suppressed until the start of your next turn.",
        "000009823005": "High Kâhl: models in bearer’s unit gain melee fight-on-death on 4+ if destroyed before fighting.",
        "000010637002": "Abhuman Detail: COMMISSAR bearer can issue Orders to OGRYN units and can attach to Ogryn Squad/Bullgryn Squad during Declare Battle Formations.",
        "000010637003": "Aquilan Eye: bearer gains Target Weak Spot Order option (ranged attacks by ordered unit improve AP by 1 vs targets within 12\").",
        "000010637004": "Spec Ops Veteran: bearer gains Move to the Shadows Order option (ranged attacks targeting the ordered unit suffer -1 to hit via Stealth-equivalent handling).",
        "000010637005": "Laud Hailer: bearer issues Orders to eligible units within 12\" instead of 6\".",
        "000010645002": "Carmine Reliquary: bearer unit gains Scouts 6\"; ADEPTUS ASTARTES within 6\" can re-roll Battle-shock tests.",
        "000010645003": "Master of the Red Thirst: once per battle start of Fight phase, bearer unit gains Fights First until end of phase.",
        "000010645004": "Sanguinary Tear (Aura): friendly Death Company within 6\" gain +1 Strength to weapons.",
        "000010645005": "Angel's Fang: bearer melee attacks vs CHARACTER/MONSTER/VEHICLE gain Sustained Hits 2.",
        "000009749002": "Dread Majesty (Aura): NECRONS units within 6\" (excluding TITANIC) re-roll Hit and Wound rolls of 1.",
        "000009749003": "Miniaturised Nebuloscope: bearer unit ranged weapons ignore cover.",
        "000009749004": "Demanding Leader: Command phase select friendly NECRONS VEHICLE/MOUNTED (non-TITANIC) within 6\" to shoot after Falling Back until next Command phase.",
        "000009749005": "Chrono-impedance Fields: Command phase select friendly NECRONS VEHICLE/MOUNTED (non-TITANIC) within 6\"; allocated damage -1 until next Command phase.",
        "000009757002": "Decoy Targets: in your Movement phase, optional single-dialog model selection (or None); selected other friendly INFANTRY model is destroyed and bearer is set up as close as possible to it (not within Engagement Range), up to twice per battle and no more than once per battle round.",
        "000009757003": "Esoteric Explosives: when targeted by the Grenades Stratagem, mortal wounds are inflicted on 3+ instead of 4+.",
        "000009757004": "Intraneural Biotech: once per battle round, bearer can be targeted with Heroic Intervention or Counter-offensive for 0CP and can still use that Stratagem even if it was already used on a different unit this phase.",
        "000009757005": "Micromelta Rounds: bearer’s exitus rifle gains [ANTI-MONSTER 4+] and [ANTI-VEHICLE 4+].",
        "000010123002": "Daemon Weapon of Nurgle: bearer melee attacks score critical hits on unmodified 5+.",
        "000010123003": "Furnace of Plagues: bearer melee weapons gain +1 Strength, +1 Attacks, and Devastating Wounds.",
        "000010123004": "Arch Contaminator: while the bearer's (attached) unit is within range of a controlled objective, attacks can re-roll Wound rolls.",
        "000010123005": "Revolting Regeneration: bearer gains Feel No Pain 5+.",
        "000010580002": "Pharmacophex: after selecting Combat Drugs each Command phase, roll D6; bearer’s unit gains the rolled Combat Drug until next Command phase unless that drug is already active army-wide.",
        "000010580003": "Chronoshard: once per battle at the start of the Fight phase, bearer unit can gain Fights First until end of phase.",
        "000010580004": "Periapt of Torments: enemy units cannot target the bearer’s unit with Fire Overwatch.",
        "000010580005": "Morghenna's Curse: bearer melee weapons gain +1 AP and +1 Damage.",
        "000010151002": "Touched by the Warp: bearer gains the PSYKER keyword.",
        "000010151003": "Eyes of Z'desh: models in the bearer's unit gain Scouts 6\".",
        "000010151004": "Mind Blade: melee weapons equipped by models in the bearer's unit gain [LANCE].",
        "000010151005": "Infernal Avatar: bearer melee weapons gain +2 Strength and +1 AP.",
        "000009819002": "Cankerblight: when an enemy (non-MONSTER/VEHICLE) within 6\" fails Battle-shock, you may destroy one model; if used, Daemonic Terror mortals are suppressed for that test.",
        "000009819003": "Maggot Maws: Shooting phase select enemy within 6\"; it takes a Battle-shock test then suffers D3 mortal wounds on 3+; Daemonic Terror mortals are suppressed for that test.",
        "000009819004": "Droning Shroud (Aura): friendly LEGIONES DAEMONICA NURGLE units within 6\" can only be targeted by ranged attacks from models within 18\".",
        "000009819005": "Font of Spores (Aura): friendly LEGIONES DAEMONICA NURGLE units within 6\" improve weapon AP by 1 for ranged and melee attacks.",
        "000009815002": "Slaughterthirst (Aura): friendly LEGIONES DAEMONICA KHORNE non-MONSTER units within 6\" gain [LANCE] on melee weapons.",
        "000009815003": "Fury's Cage: when the bearer is selected to fight, optional confirmation applies D3+1 mortal wounds to the bearer and grants bearer-only re-roll Hit and re-roll Wound rolls for melee attacks until end of phase.",
        "000009815004": "Brazenmaw: add 2 to Charge rolls for the bearer's unit.",
        "000009815005": "Gateway Unto Damnation: the bearer's Deadly Demise triggers on 2+, and after the bearer destroys one or more enemy units this battle its Deadly Demise damage becomes D3+3.",
        "000009806002": "False Majesty (Aura): friendly LEGIONES DAEMONICA SLAANESH non-MONSTER units within 6\" gain +1 to wound for melee attacks.",
        "000009806003": "Dreaming Crown (Aura): friendly LEGIONES DAEMONICA SLAANESH non-MONSTER units within 6\" gain +1 to hit for melee attacks.",
        "000009806004": "Avatar of Perfection: at phase start, if no other friendly unit is within 6\" of bearer, bearer can re-roll Advance/Charge and can ignore any/all Move, Advance, and Charge modifiers via modifier-choice decisions.",
        "000009806005": "Soul Glutton: if bearer destroys one or more enemy models with melee attacks in the Fight phase, end-of-phase optional decision rolls D3 to heal bearer wounds.",
        "000009983002": "Supernova Launcher: select one bearer Airbursting Fragmentation Projector; that selected weapon gains +3 Strength, +1 AP and +1 Damage.",
        "000009983003": "Thermoneutronic Projector: select one bearer T'au flamer; that selected weapon gains +2 Strength, +1 AP and +1 Damage.",
        "000009983004": "Plasma Accelerator Rifle: select one bearer plasma rifle; that selected weapon gains +2 Strength, +1 Attack, +1 AP and +1 Damage.",
        "000009983005": "Fusion Blades: select one bearer fusion blaster; that selected weapon gains +1 Attack, +3 Strength, and [MELTA 4].",
        "000008811002": "Coordinated Exploitation: while the bearer is leading an Observer unit, guided attacks against that unit's Spotted target gain [SUSTAINED HITS 1] until end of phase.",
        "000008811003": "Exemplar of the Mont'ka: while the bearer is leading, the bearer's unit gains Killing Blow effects during battle round 4.",
        "000008811004": "Strategic Conqueror: at the start of battle round 1, select one objective marker; while the bearer is on the battlefield, friendly T'AU EMPIRE models within range of that marker gain +1 Objective Control.",
        "000008811005": "Strike Swiftly: before Scout moves, optional single-dialog selection of up to two friendly T'AU EMPIRE units within 6\" of the bearer that do not have Scouts; selected units gain Scouts 6\" for the battle.",
        "000008385002": "Radial Suffusion: while the bearer is on the battlefield, Rad-bombardment Fallout (battle rounds 2-5) also applies to enemy units within 6\" of their deployment zone.",
        "000008385003": "Malphonic Susurrus: while the bearer is leading a unit, models in that unit gain Stealth.",
        "000008385004": "Peerless Eradicator: while the bearer is leading a unit, ranged weapons equipped by models in that unit gain [SUSTAINED HITS 1].",
        "000008385005": "Autoclavic Denunciation: ranged weapons equipped by the bearer gain [ANTI-INFANTRY 2+] and [ANTI-MONSTER 4+].",
        "000009987002": "Superior Creation: bearer-only return on a 2+ at end of phase after first destruction (full wounds).",
        "000009987003": "Praesidius: bearer gains Lone Operative and Stealth (no Lone Operative leak while attached).",
        "000009987004": "Fierce Conqueror: start of Fight phase, bearer gains +2 Attacks per 5 enemy models within 6\" until end of phase.",
        "000009987005": "Admonimortis: bearer melee weapons gain +3 Strength, +1 AP, and +1 Damage.",
        "000010493002": "Bearer of the Iron Chalice: end of Movement phase select one other friendly IMPERIAL KNIGHTS unit within 12\" and visible; it regains D3 wounds (or 3 wounds while Honoured).",
        "000010493003": "Bearer of the Evanescent Ion: end of Movement phase select one other friendly IMPERIAL KNIGHTS unit within 12\" and visible; it gains Stealth until the start of your next Movement phase.",
        "000010493004": "Bearer of the Judicant's Helm: start of Shooting phase select one other friendly IMPERIAL KNIGHTS unit within 12\" and visible; its ranged weapons gain [IGNORES COVER] until end of phase.",
        "000010493005": "Bearer of the Lancer's Sigil: start of Charge phase select one other friendly IMPERIAL KNIGHTS unit within 12\" and visible; it can re-roll Charge rolls until end of phase.",
        "000009777002": "Mandulian Reliquary: while the bearer's unit is not Battle-shocked, add 3 to the bearer's Objective Control.",
        "000009777003": "Radiant Champion: bearer melee weapons gain [PRECISION]; while bearer is wholly within Hallowed Ground, each successful wound inflicts 1 mortal wound in addition.",
        "000009777004": "Phial of the Abyss: models in the bearer's unit gain Stealth.",
        "000009777005": "Paragon of Sanctity: once per battle at start of any phase, select a friendly GREY KNIGHTS unit within 18\" and visible (or None) to count as within Hallowed Ground until end of phase.",
        "000008367002": "Follow Me Ladz: while leading, bearer unit gains +2\" Move.",
        "000008367003": "Headwoppa's Killchoppa: bearer melee weapons (excluding Extra Attacks) gain Devastating Wounds.",
        "000008367004": "Kunnin' But Brutal: while leading, bearer unit can shoot and charge after Falling Back.",
        "000008367005": "Supa-Cybork Body: bearer gains Feel No Pain 4+.",
        "000010304002": "Knight Diabolus: bearer melee weapons improve WS by 1; while using Diabolic Power, bearer melee weapons gain [LANCE].",
        "000010304003": "Blasphemous Engine: +2 Wounds; Malefic Surge Leadership test can be re-rolled.",
        "000010304004": "Fleshmetal Fusion: +1 Toughness; while using Unnatural Fortitude, bearer gains +1 armor save vs Damage 1.",
        "000010304005": "Bestial Aspect: bearer ranged weapons gain [Assault]; while using Unholy Hunger, may ignore Move/Advance modifiers.",
        "000009980002": "Leaping Shadows: models in the bearer's unit gain Scouts 9\".",
        "000009980003": "Mantle of Gloom (Aura): while enemy units are within Engagement Range of the bearer's unit, models in those units suffer -1 Objective Control.",
        "000009980004": "Fade to Darkness: end of Fight phase, if the bearer's unit destroyed one or more enemy units this phase and is not within Engagement Range, optional confirmation moves it into Strategic Reserves.",
        "000009980005": "Malice Made Manifest: start of Fight phase select one enemy unit within Engagement Range of the bearer's unit and roll one D6 (2-5: D3 mortal wounds, 6: 3 mortal wounds).",
        "000009810002": "Inescapable Eye: Command phase +1 Flux token if opponent has any and bearer is on battlefield.",
        "000009810003": "Infernal Puppeteer: in your Shooting phase, optionally measure range/LOS from a friendly visible LEGIONES DAEMONICA TZEENTCH unit within 9\".",
        "000009810004": "Neverblade: bearer melee weapons gain +2 Strength, +1 Attacks, +1 AP; +1 to hit with melee attacks.",
        "000009810005": "Improbable Shield (Aura): friendly LEGIONES DAEMONICA TZEENTCH units within 6\" gain Feel No Pain 4+ vs Psychic attacks and mortal wounds.",
    }
    if enh_id in explicit:
        return ("Supported", explicit[enh_id])

    status, notes = classify_enhancement_support(description)
    if status == "Supported":
        return (status, notes)
    return (status, notes)


def _stratagem_support(
    name: str,
    description: str = "",
    *,
    detachment_name: str = "",
    stratagem_id: str = "",
) -> Tuple[str, str, str]:
    name_u = _canon_stratagem_name(name)
    det_u = _norm(detachment_name).upper()
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
        "TUNNEL CRAWLERS": "Start of your Movement phase: selected GENESTEALER CULTS unit arriving with Deep Strike this phase can be set up more than 6\" from enemy models and cannot declare a charge this turn.",
        "LYING IN WAIT": "Start of your opponent's Movement phase: selected GENESTEALER CULTS BATTLELINE unit in Cult Ambush can be set up wholly within 6\" of its marker and outside Engagement Range this phase.",
        "PRIMED AND READIED": "Start of your Shooting/Fight phase: selected GENESTEALER CULTS unit that has not been selected this phase scores critical hits on unmodified Hit rolls of 5+ until end of phase.",
        "COORDINATED TRAP": "Start of your Shooting/Fight phase: select two eligible GENESTEALER CULTS units and one enemy unit; selected units gain +1 to Wound rolls and can only target that enemy until end of phase (Fight phase requires the enemy to be in Engagement Range of both selected units).",
        "RETURN TO THE SHADOWS": "End of your opponent's Fight phase: selected GENESTEALER CULTS INFANTRY unit not within Engagement Range is removed from the battlefield and placed into Strategic Reserves.",
        "A DEADLY SNARE": "Opponent Charge phase, just after an enemy unit declares a charge: selected GENESTEALER CULTS INFANTRY charge target rolls one D6 to deal mortal wounds to the charging unit (2-4: D3, 5+: 3).",
        "APOPLECTIC FRENZY": "Advance and Charge for a BERZERKERS unit; Berzerker Warband only.",
        "A GRIM WARNING": "Destroyed BLOOD ANGELS unit on a previously controlled objective lets you select a marker to remain under your control until broken.",
        "ARMOUR OF CONTEMPT": "Shooting/Fight phase: targeted ADEPTUS ASTARTES unit worsens AP by 1 vs the attacking unit until it finishes its attacks.",
        "BERZERKER'S WRATH": "Blood Surge distance is fixed at 8\" (no D6 roll) for a BERZERKERS unit.",
        "BERZERKER’S WRATH": "Blood Surge distance is fixed at 8\" (no D6 roll) for a BERZERKERS unit.",
        "ANTI-GRAV REPULSION": "Opponent Charge phase reaction: AELDARI VEHICLE FLY target imposes -2 to that enemy unit's Charge rolls until phase end (target-filtered modifier).",
        "ANTI‑GRAV REPULSION": "Opponent Charge phase reaction: AELDARI VEHICLE FLY target imposes -2 to that enemy unit's Charge rolls until phase end (target-filtered modifier).",
        "BLIND GRENADES": "Opponent Charge phase reaction after charge declaration: selected AGENTS OF THE IMPERIUM GRENADES unit (or VINDICARE ASSASSIN) that was declared as a charge target imposes -1 to that enemy unit's Charge roll, or -2 if the selected target is VINDICARE ASSASSIN.",
        "HYPERSTIMMS": "Opponent Shooting phase or either Fight phase defensive reaction after enemy targets are selected: selected AGENTS OF THE IMPERIUM CHARACTER unit gains +1 Toughness until end of phase; if the selected unit is an EVERSOR ASSASSIN, it also gains Feel No Pain 4+ until end of phase.",
        "ORBITAL OVERSIGHT": "Opponent Shooting phase defensive reaction after enemy targets are selected: selected AGENTS OF THE IMPERIUM INFANTRY unit can only be selected as a target of ranged attacks by attacking models within 18\", or within 6\" if that unit has Lone Operative, until end of phase.",
        "PRIME TARGET": "Your Shooting phase or either player's Fight phase: selected AGENTS OF THE IMPERIUM unit that has not yet acted re-rolls Wound rolls of 1 against CHARACTER targets until end of phase; OFFICIO ASSASSINORUM models in that unit can instead re-roll Wound rolls against the enemy WARLORD.",
        "WILL-SAPPING SALVO": "Your Shooting phase: selected AGENTS OF THE IMPERIUM INFANTRY unit that has not been selected to shoot gains [SUSTAINED HITS 1] on ranged weapons until end of phase; if selected unit is CULEXUS ASSASSIN, its ranged weapon Damage characteristic becomes 3 until end of phase.",
        "WILL‑SAPPING SALVO": "Your Shooting phase: selected AGENTS OF THE IMPERIUM INFANTRY unit that has not been selected to shoot gains [SUSTAINED HITS 1] on ranged weapons until end of phase; if selected unit is CULEXUS ASSASSIN, its ranged weapon Damage characteristic becomes 3 until end of phase.",
        "BLESSING OF BURNING BLOOD": "Shooting/Fight phase: after enemy targets; BLOOD LEGIONS unit within 6\" of targeted WORLD EATERS grants 5++ (4++ if Boon of Blood active) until end of phase.",
        "BLITZING FIREPOWER": "Shooting phase: ASURYANI unit gains Sustained Hits 1 vs targets within 12\"; if already has Sustained Hits, crits on 5+.",
        "CLOUDSTRIKE": "Movement Reinforcements start: AELDARI VEHICLE FLY in Strategic Reserves gains temporary Deep Strike with >6\" setup; on arrival cannot charge this turn; affected Transports enforce >6\" disembark distance and no-charge for disembarking units this turn.",
        "DEATH ANSWERS DEATH": "End of opponent Shooting phase: select one YNNARI unit (excluding WRAITH CONSTRUCT) that lost one or more models this phase; that unit can shoot as if it were your Shooting phase.",
        "EMISSARIES OF YNNEAD": "Fight phase, just after a friendly YNNARI INFANTRY unit selects targets: until end of phase, re-roll Hit rolls of 1 for its attacks (or re-roll the Hit roll while below Starting Strength).",
        "MACABRE RESILIENCE": "Opponent Shooting phase or the Fight phase, just after an enemy unit selects targets: selected YNNARI INFANTRY or YNNARI MOUNTED unit (excluding WRAITH CONSTRUCT) subtracts 1 from wound rolls for attacks that target it until end of phase.",
        "DOOM INESCAPABLE": "Your Shooting phase: AVATAR OF KHAINE model not yet selected to shoot sets Wailing Doom ranged profile to Range 18\" and Damage 8 until end of phase.",
        "DEATHLESS DUTY": "Fight phase: DEATH COMPANY unit fights on death after the attacker finishes its attacks (until end of phase).",
        "FEIGNED RETREAT": "Movement phase: ASURYANI unit that Fell Back can shoot and charge this turn.",
        "FIRE AND FADE": "Shooting phase: ASURYANI INFANTRY makes Normal move D6+1\" after shooting; cannot charge or embark this turn.",
        "INSENSATE RAMPAGE": "Defensive reaction after targets selected: DEATH COMPANY unit gains Feel No Pain 5+ until end of phase.",
        "KHAINE'S VENGEANCE": "Opponent Movement phase reaction after an eligible enemy is selected to Fall Back: selected ASPECT WARRIORS/AVATAR OF KHAINE unit in Engagement Range forces that enemy unit to take Desperate Escape tests (Battle-shocked enemies take them at -1).",
        "KHAINE’S VENGEANCE": "Opponent Movement phase reaction after an eligible enemy is selected to Fall Back: selected ASPECT WARRIORS/AVATAR OF KHAINE unit in Engagement Range forces that enemy unit to take Desperate Escape tests (Battle-shocked enemies take them at -1).",
        "LIGHTNING-FAST REACTIONS": "Shooting/Fight phase: targeted ASURYANI (non-Wraith Construct) gets -1 to hit until end of phase.",
        "PALL OF DREAD": "Any phase: when a friendly YNNARI unit is just destroyed while within range of a previously controlled objective marker, select one such marker; it remains under your control until your opponent's Level of Control is greater at end of a phase.",
        "PARTING THE VEIL": "Fight phase, just after an enemy unit selects targets: selected YNNARI unit fights on death in melee automatically after the attacker finishes its attacks until end of phase.",
        "PRETERNATURAL PRECISION": "Your Shooting phase: selected ASPECT WARRIORS unit not yet selected to shoot can optionally spend one Aspect Shrine token, then chooses one (or two if spent) of [IGNORES COVER], [LETHAL HITS], [SUSTAINED HITS 1] for its ranged weapons until end of phase.",
        "SKYBORNE SANCTUARY": "End of Fight phase: ASURYANI unit not engaged and wholly within 6\" can embark in friendly Transport.",
        "TO THEIR FINAL BREATH": "Fight phase defensive reaction after enemy targets are selected: selected ASPECT WARRIORS/AVATAR OF KHAINE unit can optionally spend one Aspect Shrine token, then gains melee fight-on-death after attacker finishes attacks (4+, or 3+ if token was spent) until end of phase.",
        "BLOODY DANCE": "End of opponent Charge phase: selected HARLEQUINS INFANTRY or MOUNTED unit within 6\" of one or more enemy units it can charge can declare an out-of-turn charge; it gains no charge bonus this turn.",
        "CLOAK AND SHADOW": "Opponent Shooting phase reaction after enemy targets are selected: selected AELDARI INFANTRY unit within range of a controlled objective gains Stealth and can only be targeted by ranged attacks from within 18\" until end of phase.",
        "EXIT THE STAGE": "End of opponent Fight phase: selected HARLEQUINS unit not in Engagement Range is removed from the battlefield and placed into Strategic Reserves.",
        "HEROES' FALL": "Fight phase defensive reaction after enemy targets are selected: selected HARLEQUINS unit gains melee fight-on-death on 4+ until end of phase.",
        "HEROES’ FALL": "Fight phase defensive reaction after enemy targets are selected: selected HARLEQUINS unit gains melee fight-on-death on 4+ until end of phase.",
        "MOCKING FLIGHT": "Your Movement phase reaction after a HARLEQUINS unit Falls Back: selected unit can shoot and declare a charge this turn despite Falling Back.",
        "STAGED DEATH": "Any phase reaction before removal: selected just-destroyed HARLEQUINS CHARACTER model returns to the battlefield at the end of that phase as close as possible to where it was destroyed, not within Engagement Range, with half its Starting Wounds (once per battle per model).",
        "OUTCAST AMBUSH": "Your Shooting phase: selected Rangers or Shroud Runners unit that has not been selected to shoot gains [IGNORES COVER], [RAPID FIRE 1], and improves AP by 1 on ranged attacks until end of phase.",
        "INTO THE BREACH": "Your Shooting phase reaction after an ANHRATHE unit destroys one or more enemy units with shooting: selected unit can make a Normal move of up to D6+1\" after resolving its attacks.",
        "IMPEDING FIRE": "Start of opponent Charge phase: selected Rangers, Shroud Runners, or Starfangs unit chooses one visible non-TITANIC enemy unit within 36\"; that enemy unit suffers -2 to Charge rolls until phase end, not cumulative with other negative Charge modifiers.",
        "LETHAL RUSE": "Your Movement phase reaction after an AELDARI unit Falls Back: selected unit can declare a charge this turn despite Falling Back; if selected unit has ANHRATHE, also select one enemy unit it was within Engagement Range of at phase start and roll 6D6, dealing 1 mortal wound for each 4+.",
        "NO PREY TOO BIG": "Your Shooting phase: selected ANHRATHE, Rangers, or Shroud Runners unit that has not been selected to shoot gains +1 to Wound rolls for attacks whose Strength is lower than the target unit's highest Toughness until end of phase.",
        "PIRATES' DUE": "Fight phase: selected AELDARI unit that has not been selected to fight re-rolls Wound rolls of 1 until end of phase; if selected unit has ANHRATHE, it can instead re-roll Wound rolls against enemy units within range of objective markers.",
        "RAIDERS' SPOILS": "Command phase: selected ANHRATHE unit within Engagement Range gains +1 Objective Control until the start of the next Command phase.",
        "RAIDERS’ SPOILS": "Command phase: selected ANHRATHE unit within Engagement Range gains +1 Objective Control until the start of the next Command phase.",
        "COST OF VICTORY": "End of opponent Fight phase: selected GUARDIANS unit not in Engagement Range enters Strategic Reserves and returns every destroyed GUARDIANS model to that unit.",
        "BLADES OF ASURYAN": "Your Shooting phase: selected Dire Avengers or Guardians unit that has not been selected to shoot gains [PISTOL] on ranged weapons until end of phase.",
        "SHIELD NODES": "Opponent Shooting phase or the Fight phase, just after an enemy unit selects targets: selected Dire Avengers or Guardians unit that was targeted by that enemy unit imposes -1 to wound against attacks that target it this phase while it is within range of one or more objective markers.",
        "RUTHLESS KILLERS": "Your Shooting phase or the Fight phase: selected Corsair Voidscarred unit that has not been selected to shoot/fight gains +1 to the Damage characteristic of its attacks until end of phase.",
        "TIME TO STRIKE": "Your Movement phase: selected Storm Guardians unit that has not been selected to move gains fixed Advance distance 6 this phase and is eligible to shoot and declare a charge this turn after Advancing.",
        "PRESENTIMENT OF DREAD": "Command phase: selected ASURYANI PSYKER model chooses one visible enemy unit within 18\"; that enemy unit must take a Battle-shock test at -1.",
        "FOREWARNED": "Fight phase reaction after enemy targets are selected: selected ASURYANI INFANTRY unit (excluding WRAITH CONSTRUCT) targeted by that enemy and within 9\" of a friendly ASURYANI PSYKER imposes -1 to hit and -1 to wound against attacks that target it until end of phase.",
        "SEER'S EYE": "Your Shooting phase or the Fight phase: select one AELDARI PSYKER model, one friendly WRAITH CONSTRUCT unit within 12\" of it that has not been selected to shoot/fight, and one enemy unit visible to that PSYKER; attacks by that WRAITH unit against that enemy can ignore AP/Damage modifiers until end of phase.",
        "SEER’S EYE": "Your Shooting phase or the Fight phase: select one AELDARI PSYKER model, one friendly WRAITH CONSTRUCT unit within 12\" of it that has not been selected to shoot/fight, and one enemy unit visible to that PSYKER; attacks by that WRAITH unit against that enemy can ignore AP/Damage modifiers until end of phase.",
        "SOUL BRIDGE": "Your Command phase: selected WRAITHBLADES/WRAITHGUARD/WRAITHLORD unit and one ASURYANI PSYKER model are linked; until the start of your next Command phase, that WRAITH unit counts as within 12\" of that PSYKER for Psychic Guidance and Spirit Guides.",
        "SPIRIT TOKEN": "Start of your Movement phase: selected WRAITHBLADES or WRAITHGUARD unit chooses one objective marker you control within range; that marker becomes sticky under your control until your opponent's Level of Control is greater at the end of a phase.",
        "BLADES FROM BEYOND": "Your Fight phase: selected WRAITHBLADES, WRAITHLORD, or WRAITHKNIGHT unit that has not been selected to fight gains [DEVASTATING WOUNDS] on melee weapons until end of phase.",
        "CRUSHING STRIDES": "Your Charge phase, just after a WRAITHBLADES, WRAITHLORD, or WRAITHKNIGHT unit ends a Charge move: select one enemy unit in Engagement Range and roll D6s by unit type (WRAITHBLADES: one per model, WRAITHLORD: 4D6, WRAITHKNIGHT: 6D6); each 3+ deals 1 mortal wound.",
        "WRAITHBONE ARMOUR": "Opponent Shooting phase or the Fight phase reaction after enemy targets are selected: selected non-TITANIC WRAITH CONSTRUCT unit that was targeted reduces incoming Damage by 1 until end of phase.",
        "WIND OF BLADES": "Your Movement phase: selected ASURYANI MOUNTED or VYPER unit that has not been selected to move can shoot and declare a charge this turn after it Advances or Falls Back.",
        "DARING RIDERS": "Start of your Movement phase: selected ASURYANI MOUNTED or VYPER unit in Reserves that can arrive this turn can be set up more than 6\" horizontally from enemy models this phase, and if set up within 9\" of one or more enemy units it cannot declare a charge this turn.",
        "FOCUSED FIREPOWER": "Your Shooting phase: selected ASURYANI MOUNTED or VYPER unit that has not been selected to shoot this phase improves AP by 1 for each of its attacks until end of phase.",
        "DEATH FROM ON HIGH": "Your Shooting phase or the Fight phase: selected ASURYANI MOUNTED or VYPER unit that was set up from Reserves this turn and has not been selected this phase can re-roll Wound rolls until end of phase.",
        "OVERFLIGHT": "End of your Shooting phase or the end of the Fight phase: selected ASURYANI MOUNTED unit that destroyed one or more enemy units this phase can make a Normal move of up to 7\".",
        "SPIRALLING EVASION": "Opponent's Shooting phase after enemy targets are selected: selected ASURYANI MOUNTED or VYPER unit targeted by that enemy gains a 4+ invulnerable save until end of phase.",
        "VENOMOUS WRATH": "Your Shooting phase: selected HARLEQUINS VEHICLE unit that has not been selected to shoot can make a Normal move up to 6\" after it shoots if it is not within Engagement Range, and it is not eligible to declare a charge until end of turn.",
        "FANGS OF THE BROOD": "Start of the Fight phase: selected TROUPE unit can gain all three Dance of Death abilities this phase instead of one.",
        "STRIKING STRIDE": "Your Charge phase: selected HARLEQUINS unit is eligible to declare a charge in a turn in which it Advanced until end of phase.",
        "SKYWARD LUNGE": "End of opponent Fight phase: selected HARLEQUINS VEHICLE or HARLEQUINS MOUNTED unit that is not in Engagement Range is removed and placed into Strategic Reserves.",
        "WEAVERS' COILS": "End of your Fight phase: selected HARLEQUINS MOUNTED unit that was eligible to fight this phase can make a Normal move, or can make a Fall Back move of up to 6\" if it is within Engagement Range.",
        "WEAVING STRIDE": "Opponent Movement phase reaction after an enemy unit ends a Normal, Advance, or Fall Back move: selected HARLEQUINS INFANTRY unit within 9\" can make a Normal move up to 6\".",
        "UNSHROUDED TRUTH": "Your Movement phase: selected ASURYANI INFANTRY unit (excluding WRAITH CONSTRUCT) that has not been selected to move this phase, was not set up this phase, and is within 9\" of a friendly ASURYANI PSYKER is removed and set up again more than 9\" horizontally from all enemy models; until end of phase it is not eligible to be selected to move.",
        "FATE INESCAPABLE": "Your Shooting phase: selected ASURYANI INFANTRY unit (excluding WRAITH CONSTRUCT) that has not been selected to shoot this phase and is within 9\" of a friendly ASURYANI PSYKER gains [IGNORES COVER] on ranged weapons, and each time it makes an attack on a Critical Wound that attack improves AP by 1, until end of phase.",
        "ISHA'S FURY": "Opponent Movement phase, just after an enemy unit ends a Normal, Advance, or Fall Back move: selected ASURYANI PSYKER model within 9\" of that enemy rolls six D6; for each 3+, that enemy unit suffers 1 mortal wound.",
        "PSYCHIC SHIELD": "Opponent Shooting phase, just after an enemy unit has selected its targets: selected ASURYANI INFANTRY unit (excluding WRAITH CONSTRUCT) that was selected as a target and is within 9\" of a friendly ASURYANI PSYKER can only be selected as a target of ranged attacks from within 18\" until end of phase.",
        "VAUL'S VENGEANCE": "Opponent Shooting phase or the Fight phase, just after an enemy unit destroys one of your Dire Avengers or Guardians units: selected War Walkers unit can shoot as if it were your Shooting phase after that enemy finishes its attacks, and those attacks can only target that enemy unit (once per battle round).",
        "VAUL’S VENGEANCE": "Opponent Shooting phase or the Fight phase, just after an enemy unit destroys one of your Dire Avengers or Guardians units: selected War Walkers unit can shoot as if it were your Shooting phase after that enemy finishes its attacks, and those attacks can only target that enemy unit (once per battle round).",
        "TRICKSTERS' RETORT": "Opponent Movement phase reaction after an enemy unit ends a Normal, Advance, or Fall Back move: selected TROUPE unit within 9\" of that enemy unit can make a Normal move up to 6\".",
        "TRICKSTERS’ RETORT": "Opponent Movement phase reaction after an enemy unit ends a Normal, Advance, or Fall Back move: selected TROUPE unit within 9\" of that enemy unit can make a Normal move up to 6\".",
        "WARDING SALVOES": "Your Shooting phase or the Fight phase: selected Dire Avengers or Guardians unit that has not been selected to shoot/fight can re-roll wound rolls for attacks that target enemy units within range of one or more objective markers until end of phase.",
        "YRIEL'S EXAMPLE": "Fight phase defensive reaction after enemy targets are selected: selected AELDARI INFANTRY unit (excluding WRAITH CONSTRUCT) targeted by that enemy unit gains Feel No Pain 5+ until end of phase.",
        "YRIEL’S EXAMPLE": "Fight phase defensive reaction after enemy targets are selected: selected AELDARI INFANTRY unit (excluding WRAITH CONSTRUCT) targeted by that enemy unit gains Feel No Pain 5+ until end of phase.",
        "WITHDRAW AND REINFORCE": "End of opponent Fight phase: selected ANHRATHE unit not in Engagement Range enters Strategic Reserves; if below Starting Strength, all destroyed non-CHARACTER models are returned to that unit.",
        "VENGEFUL SORROW": "Opponent Shooting phase reaction after enemy shooting resolves: selected AELDARI INFANTRY unit that lost models and is not Battle-shocked/engaged can make a Surge move of up to D6+1\" toward the closest non-AIRCRAFT enemy unit (can enter Engagement Range).",
        "WEBWAY TUNNEL": "End of opponent Fight phase: ASURYANI INFANTRY wholly within 9\" of battlefield edge goes to Strategic Reserves.",
        "BLOOD OFFERING": "Sticky objective on unit destruction; Berzerker Warband only.",
        "DAEMONIC RESISTANCE": "Shooting/Fight defensive reaction after enemy targets are selected: WORLD EATERS POSSESSED unit gains -1 to wound against the attacking unit until end of phase.",
        "DAEMONIC FURY": "Fight phase: BLOOD LEGIONS unit selects WORLD EATERS unit within 6\" to gain [LANCE] until end of turn; if Daemonic Rage active, also [TWIN-LINKED] this phase.",
        "DAEMONIC STRENGTH": "Fight phase: WORLD EATERS POSSESSED unit (not fought) gains conditional +1 Damage for melee attacks this phase (Eightbound vs non-MONSTER/VEHICLE; Exalted Eightbound vs MONSTER/VEHICLE).",
        "DAEMONTIDE": "Command phase: WORLD EATERS unit selects BLOOD LEGIONS within 6\" to return destroyed models (1 Mounted / D3 Beast / D6 Infantry).",
        "FRENZIED RESILIENCE": "Fight phase: after enemy targets; WORLD EATERS unit reduces damage by 1.",
        "HACK AND SLASH": "Fight phase: charged WORLD EATERS unit gains +1 AP on melee weapons.",
        "LAYERED WARDS": "Any phase reaction after a mortal wound allocation: targeted AELDARI VEHICLE gains Feel No Pain 5+ against mortal wounds until end of phase.",
        "PLAGUESURGE": "Command phase: your DEATH GUARD WARLORD on battlefield gains +3\" Contagion Range until the start of your next Command phase.",
        "LEECHSPORE ERUPTION": "Command phase: wounded DEATH GUARD model rolls D6s equal to wounds lost; on each 5+ deal 1 mortal to an enemy within 3\" and heal 1 (both capped at 6).",
        "OVERWHELMING GENEROSITY": "Start of Shooting phase: mark one visible enemy unit; DEATH GUARD units can re-roll attack-count dice when making ranged attacks that target it this phase.",
        "CREEPING BLIGHT": "Shooting phase: selected DEATH GUARD INFANTRY unit (not yet selected to shoot) re-rolls ranged Hit and Wound rolls vs Afflicted targets this phase.",
        "PUTRID DETONATION": "Any phase reaction: just-destroyed DEATH GUARD VEHICLE/MONSTER with Deadly Demise auto-explodes and enemy units damaged by it become Afflicted until your next turn.",
        "SOULSIGHT": "Your Shooting phase: targeted AELDARI VEHICLE not yet selected to shoot gains one Hit, one Wound, and one Damage re-roll each time it is selected to shoot this phase.",
        "WARRIOR FOCUS": "Your Shooting phase or the Fight phase: selected ASPECT WARRIORS/AVATAR OF KHAINE unit not yet selected to act can ignore modifiers to Ballistic Skill, Weapon Skill, Hit roll, Strength, AP, and Damage characteristics until end of phase.",
        "HORRIFYING VIOLENCE": "Opponent Command phase: eligible engaged WORLD EATERS POSSESSED unit triggers Battle-shock tests at -1 for enemy units in its Engagement Range.",
        "IMMORTAL FURY": "Fight phase defensive reaction: targeted WORLD EATERS POSSESSED unit (not fought) can fight on death this phase after the attacker finishes its attacks.",
        "A WORTHY SKULL": "Fight phase: after CHARACTER/MONSTER kill, gain D3 Blood Tithe points and optionally activate Blood Tithe.",
        "RAPID MANIFESTATION": "Movement phase: EXALTED EIGHTBOUND in Reserves with Deep Strike can be set up more than 6\" away this turn and cannot declare a charge this turn.",
        "SKULLS FOR THE SKULL THRONE!": "Fight phase: after CHARACTER/MONSTER kill, roll Blessings for a unit-only extra blessing.",
        "MURDER-CALL": "End of opponent Fight phase: BLOOD LEGIONS unit not in Engagement Range goes to Strategic Reserves.",
        "SUMMONED BY SLAUGHTER": "Any phase: set up BLOODLETTERS from Reserves wholly within 9\" of destroyed model; >6\" from enemies; once per battle round.",
        "WARP STALKERS": "Movement/Charge phase: WORLD EATERS POSSESSED unit can move through enemy models (including MONSTER/VEHICLE), gains phase move-through handling, and auto-passes Desperate Escape for the phase.",
        "BLOODTHIRSTY HORDE": "Fight phase: JAKHALS/GOREMONGERS unit in Engagement Range (not yet fought) gains fight eligibility out to 3\" while still requiring the target enemy unit to be within Engagement Range of the attacking unit.",
        "BLOODY VENGEANCE": "Any phase: when your WORLD EATERS MONSTER/TITANIC unit is destroyed, mark the destroying enemy unit; JAKHALS/GOREMONGERS can re-roll Hit rolls against that enemy unit until end of battle.",
        "BRAZEN IDOL": "Your Command phase: WORLD EATERS MONSTER/TITANIC target chooses an Idols of Khorne mode (Infinite Rage/Burning Wrath/Blessed Blood) as a source-specific override until your next Command phase; once per battle.",
        "DRAWN TO THE SLAUGHTER": "Any phase: when your JAKHALS unit is destroyed, add an identical replacement unit at Starting Strength into Strategic Reserves; once per battle and disallows returning destroyed CHARACTER units to Attached units.",
        "FAIL NOT THE BLOOD GOD": "Fight phase: JAKHALS/GOREMONGERS unit re-rolls Hit rolls of 1; upgrades to full Hit re-rolls while within MONSTER/TITANIC Idol range.",
        "IN THE SHADOW OF BRASS IDOLS": "Opponent Shooting phase or Fight phase defensive reaction: targeted JAKHALS/GOREMONGERS gain Feel No Pain 6+ (or 5+ while within MONSTER/TITANIC Idol range) until end of phase.",
        "ASPIRE TO INFAMY": "Fight phase: KHORNE BERZERKERS/JAKHALS unit within 8\" of friendly WORLD EATERS CHARACTER (not yet fought) gives non-CHARACTER models +1 Strength and +1 AP to melee weapons until end of phase.",
        "BRAZEN CONTEMPT": "Opponent Shooting phase reaction: targeted WORLD EATERS unit gets -1 to be wounded by ranged attacks if Strength > Toughness, or always if the target unit contains a VESSEL OF WRATH model.",
        "GORY DEDICATION": "End of Fight phase: WORLD EATERS unit that made melee kills this phase can make an objective it controls sticky.",
        "MEET FORCE WITH FORCE": "Opponent Shooting phase reaction: WORLD EATERS INFANTRY/MOUNTED/DAEMON PRINCE unit that lost wounds can make a Blood Surge move (D6, with optional reroll for KHORNE BERZERKERS or VESSEL OF WRATH units).",
        "OVERSHADOWED BY NONE": "Fight phase: WORLD EATERS INFANTRY/MOUNTED/DAEMON PRINCE unit not yet fought can re-roll melee Wound rolls against MONSTER/VEHICLE targets until end of phase.",
        "PUNISH THE CRAVEN": "Opponent Movement phase reaction: WORLD EATERS INFANTRY/DAEMON PRINCE unit in Engagement Range of an enemy selected to Fall Back forces Desperate Escape tests; VESSEL OF WRATH targets impose an additional -1 modifier.",
        "AGGRESSIVE DISEMBARKATION": "Movement phase: WORLD EATERS RHINO disembarks one embarked unit wholly within 6\" and can set up within Engagement Range.",
        "ENDLESS PURSUIT OF VIOLENCE": "End of Fight phase: WORLD EATERS INFANTRY wholly within 6\" can embark in a friendly Transport.",
        "FULL-THROTTLE ASSAULT": "Movement phase: WORLD EATERS RHINO allows disembarking units to charge after a Normal move this phase.",
        "FURY UNLEASHED": "Opponent Shooting phase: hit WORLD EATERS RHINO disembarks a KHORNE BERZERKERS unit to make a Blood Surge move (mutually exclusive with Unrelenting Advance).",
        "SMASH THROUGH": "Movement phase: WORLD EATERS VEHICLE can move horizontally through terrain on Normal/Advance moves this phase.",
        "SWIFT DEPLOYMENT": "Your Movement phase after an AELDARI TRANSPORT Advances: that transport can disembark units after advancing this phase; those disembarked units count as Normal moved and cannot charge this turn.",
        "UNRELENTING ADVANCE": "Opponent Shooting phase: hit WORLD EATERS VEHICLE can make a Normal move up to 6\" (mutually exclusive with Fury Unleashed).",
        "THE FOE FORESEEN": "Shooting/Fight phase: targeted ADEPTUS ASTARTES unit worsens AP by 1 vs the attacking unit until it finishes its attacks.",
        "ARMOUR OF ABHORRENCE": "Shooting/Fight phase defensive reaction after enemy targets selected: targeted EMPEROR'S CHILDREN unit worsens the AP characteristic of incoming attacks by 1 until the attacking unit finishes its attacks.",
        "CAPRICIOUS REACTIONS": "Opponent Shooting phase defensive reaction after enemy targets selected: targeted EMPEROR'S CHILDREN unit imposes -1 to hit until end of phase.",
        "COMBAT STIMMS": "Fight phase defensive reaction after enemy targets selected: targeted EMPEROR'S CHILDREN INFANTRY unit imposes -1 to wound until end of phase.",
        "EMBRACE THE PAIN": "Fight phase start reaction: selected EMPEROR'S CHILDREN INFANTRY unit forces enemy units in Engagement Range to target it when selecting Fight targets this phase.",
        "MARTIAL PERFECTION": "Fight phase reaction when selected to fight: chosen EMPEROR'S CHILDREN unit gains full Hit re-rolls until end of phase.",
        "PROTECTION OF THE DARK PRINCE": "Any phase reaction when an attack/mortal wound is allocated: selected EMPEROR'S CHILDREN unit gains Feel No Pain 6+ (4+ against mortal wounds) until end of phase.",
        "UNSHAKEABLE OPPONENTS": "Your Command phase: selected EMPEROR'S CHILDREN unit can ignore any/all Ballistic Skill, Weapon Skill, Hit roll and Wound roll modifiers until end of turn (choice-driven at roll resolution).",
        "UNBOUND ARROGANCE": "Coterie of the Conceited pledge increases by 1 (once per battle round).",
        "CRUEL BLADESMAN": "Fight phase: charged unit gains +1 AP on melee weapons (before it has fought).",
        "CUT DOWN THE WEAK": "Opponent Movement phase reaction when an enemy unit Falls Back: select an eligible EMPEROR'S CHILDREN unit within 6\" to attempt an out-of-turn charge against that enemy (does not count as having charged).",
        "DEATH ECSTASY": "Opponent Fight phase defensive reaction after enemy targets are selected: targeted EMPEROR'S CHILDREN unit fights on death after the attacker finishes its attacks this phase.",
        "TERRIFYING SPECTACLE": "Opponent Command phase: select an EMPEROR'S CHILDREN unit that charged and destroyed an enemy last turn; enemy units within 6\" take Battle-shock tests (Below Half-strength units suffer an extra -1).",
        "ADVANCE AND CLAIM": "Your Command phase: selected EMPEROR'S CHILDREN TRANSPORT with an embarked, non-Battle-shocked TORMENTORS unit can make a selected objective marker sticky.",
        "CEASELESS ONSLAUGHT": "Your Charge phase: selected EMPEROR'S CHILDREN unit that disembarked this turn from a friendly TRANSPORT after its Normal move can declare a charge this phase.",
        "DYNAMIC BREAKTHROUGH": "Your Movement phase: selected EMPEROR'S CHILDREN VEHICLE that has not moved gains move/advance/fall back through-enemy-model handling and auto-passes Desperate Escape tests this phase.",
        "ONTO THE NEXT": "Fight phase: selected EMPEROR'S CHILDREN unit that destroyed an enemy this phase can embark into an eligible friendly TRANSPORT wholly within 6\".",
        "OUTFLANKING STRIKE": "End of opponent Fight phase: move one (or two if both are DEDICATED TRANSPORT) EMPEROR'S CHILDREN TRANSPORT units wholly within 9\" of a battlefield edge into Strategic Reserves.",
        "REACTIVE DISEMBARKATION": "Opponent Shooting phase defensive reaction after enemy targets are selected: selected EMPEROR'S CHILDREN TRANSPORT queues a decision to disembark up to one embarked EMPEROR'S CHILDREN unit within 6\".",
        "LIMB FROM LIMB": "Fight phase: charged BLOOD ANGELS unit gains +1 Strength or +1 AP; Red Thirst grants both and applies Battle-shock until end of phase.",
        "RED WRATH": "Movement phase: advanced BLOOD ANGELS unit chooses shoot or charge; Red Thirst grants both and applies Battle-shock until end of turn.",
        "A CHALLENGE MET": "End of opponent Movement phase reaction: WYCH CULT unit within 9\" charges an enemy unit that moved or was set up this phase; successful charge grants no Charge bonus.",
        "ENSNARING TRAP": "End of opponent Charge phase reaction: selected AGENTS OF THE IMPERIUM INFANTRY unit within 6\" of an enemy unit it can charge attempts an out-of-turn charge that does not count as charged; if the selected unit is a CALLIDUS ASSASSIN and the charge succeeds, it gains +1 to melee wound rolls until end of turn.",
        "AGGRESSIVE MOBILITY": "Movement phase: selected T'AU EMPIRE unit that has not been selected to move treats its Advance distance this phase as a fixed +6\" (no Advance roll).",
        "AUTOMATED REPAIR DRONES": "Command phase: selected T'AU EMPIRE BATTLESUIT unit heals one selected BATTLESUIT model for D3+1 lost wounds.",
        "COMBAT DEBARKATION": "Your Shooting phase: selected T'AU EMPIRE INFANTRY unit that disembarked from a friendly TRANSPORT this turn can re-roll Wound rolls when making attacks that target the closest eligible enemy unit until end of phase.",
        "COUNTERFIRE DEFENCE SYSTEMS": "Opponent Shooting phase reaction after enemy targets are selected: selected T'AU EMPIRE unit reduces the Damage characteristic of attacks allocated to it by 1 until end of phase.",
        "FOCUSED FIRE": "Start of your Shooting phase: select two T'AU EMPIRE units that have not been selected to shoot and one enemy unit; selected friendly units can only target that enemy unit and improve AP by 1 for those attacks until end of phase (cannot be used in battle rounds 4-5).",
        "ARDENT AUTOMATA": "Movement phase reaction after a RUBRICAE unit Falls Back: selected unit can shoot and declare a charge this turn despite Falling Back.",
        "IMPLACABLE GUARDIANS": "Opponent Shooting phase defensive reaction after enemy targets are selected: selected RUBRIC MARINES PSYKER unit reduces the Damage characteristic of incoming attacks by 1 this phase, excluding attacks allocated to PSYKER models.",
        "INFERNAL FUSILLADE": "Shooting phase: selected THOUSAND SONS PSYKER unit not yet selected to shoot has inferno bolt pistol/boltguns/combi-bolters/combi-weapons gain [PSYCHIC] and set Strength 5 until end of phase.",
        "UNWAVERING PHALANX": "Opponent Charge phase reaction after an enemy unit ends a Charge move: selected RUBRIC MARINES unit within Engagement Range of that enemy imposes -1 to Wound rolls for attacks that target it until end of turn.",
        "ADRENAL SURGE": "Fight phase: selected TYRANIDS unit gains melee critical hits on 5+ this phase; can target up to two eligible TYRANIDS units when both are within Synapse Range.",
        "DEATH FRENZY": "Fight phase defensive reaction after enemy targets are selected: selected TYRANIDS unit gains melee fight-on-death on 4+ after the attacker finishes its attacks this phase.",
        "ENDLESS SWARM": "Command phase: selected ENDLESS MULTITUDE unit with destroyed models returns up to D3+3 destroyed models, or target up to two such units when both are within Synapse Range.",
        "PREDATORY IMPERATIVE": "Command phase: selected TYRANIDS unit gains one additional chosen Hyper-adaptation until your next Command phase (cannot pick the battle-round-1 adaptation); can target up to two units when both are within Synapse Range.",
        "RAPID REGENERATION": "Opponent Shooting phase or either Fight phase defensive reaction after enemy targets are selected: selected TYRANIDS unit gains Feel No Pain 6+ this phase, improving to 5+ while within Synapse Range.",
        "REACTIVE IMPACT DAMPENERS": "Shooting/Fight phase reaction after enemy targets are selected: selected T'AU EMPIRE BATTLESUIT unit imposes -1 to wound while attacker Strength is greater than target Toughness until end of phase.",
        "EXPERIMENTAL WEAPONRY": "Shooting phase: selected T'AU EMPIRE unit not yet selected to shoot can re-roll attack-count dice for its weapons until end of phase.",
        "EXPERIMENTAL AMMUNITION": "Shooting phase: selected T'AU EMPIRE unit not yet selected to shoot gains +1 Strength on ranged weapons, or +1 Strength/+1 AP and [HAZARDOUS] until end of phase (cannot target same unit as THREAT ASSESSMENT ANALYSER this phase).",
        "PINPOINT COUNTER-OFFENSIVE": "Any phase reaction when your non-KROOT T'AU EMPIRE unit is destroyed: mark the destroying enemy unit until end of battle; non-KROOT T'AU EMPIRE units can re-roll Hit rolls when targeting that enemy unit.",
        "PULSE ONSLAUGHT": "Your Shooting phase reaction just after a non-KROOT T'AU EMPIRE INFANTRY unit from your army has shot: select one enemy non-MONSTER/non-VEHICLE unit hit by one or more of those attacks; it is shaken (-2 Move, -2 Advance, -2 Charge) until the end of your opponent's next turn.",
        "INEXORABLE ADVANCE": "Movement phase: selected RUBRICAE unit can ignore Move/Advance modifiers and gains [ASSAULT] on ranged weapons until end of turn.",
        "NEUROWEB SYSTEM JAMMER": "Opponent Shooting phase reaction after enemy targets are selected: selected T'AU EMPIRE CRISIS unit can only be selected as the target of ranged attacks from within 18\" until end of phase.",
        "OVERRUN": "Fight phase reaction before a TYRANIDS unit consolidates: selected unit consolidates up to 6\" if it can end in Engagement Range; if within Synapse Range and not within Engagement Range, it can make a 6\" Normal move instead.",
        "REVENGE OF THE RUBRICAE": "Opponent Shooting phase reaction after a THOUSAND SONS PSYKER model is destroyed: select one friendly RUBRICAE unit within 6\" of that destroyed model; after the attacker finishes shooting, selected unit can shoot reactively only into that attacker.",
        "THREAT ASSESSMENT ANALYSER": "Shooting phase: selected T'AU EMPIRE unit not yet selected to shoot gains [SUSTAINED HITS 1] or [LETHAL HITS], or gains all three [SUSTAINED HITS 1]/[LETHAL HITS]/[HAZARDOUS] until end of phase (cannot target same unit as EXPERIMENTAL AMMUNITION this phase).",
        "BERSERK FUGUE": "Fight phase defensive reaction after targets selected: targeted WYCH CULT unit fights on death after attacker finishes attacks until end of phase.",
        "DEADLY DEBUT": "Fight phase: DRUKHARI unit that charged and has not fought gains melee Lethal Hits; WYCHES units also gain +1 AP on melee weapons until end of phase.",
        "FEIGNED WEAKNESS": "Movement phase: DRUKHARI unit that Fell Back can shoot and charge this turn.",
        "PRETERNATURAL AGILITY": "Start of Movement/Charge phase: WYCH CULT unit can ignore move/advance/charge modifiers this phase and can move through models on Normal/Advance/Charge moves until end of turn.",
        "BALEFUL BLESSING": "Any phase reaction after a HERETIC ASTARTES unit is allocated a mortal wound: that unit gains Feel No Pain 5+ against mortal wounds until end of phase.",
        "BEAUTIFUL DEATH": "Opponent Fight phase defensive reaction after enemy targets selected: targeted EMPEROR'S CHILDREN CHARACTER unit fights on death on 4+ (add 1 if Favoured Champions) after attacker finishes attacks this phase.",
        "CATALYTIC STIMULUS": "Opponent Shooting phase reaction after enemy shooting resolves and a unit lost wounds: that unit can make a reactive Stimulus move of up to D6\" toward the closest enemy non-AIRCRAFT unit (can move within Engagement Range).",
        "CLOSE-QUARTERS EXCRUCIATION": "Shooting phase: selected EMPEROR'S CHILDREN unit not yet selected to shoot gains +1 Strength and +1 AP on ranged attacks that target units within 12\" until end of phase.",
        "CONTEMPTUOUS DISREGARD": "Shooting/Fight phase defensive reaction after enemy targets selected: targeted EMPEROR'S CHILDREN unit imposes -1 to wound this phase when attacker Strength is greater than target Toughness.",
        "CRUEL RAIDERS": "End of opponent Fight phase: selected EMPEROR'S CHILDREN unit wholly within 9\" of a battlefield edge and not within 3\" horizontally of enemy units is placed into Strategic Reserves.",
        "DARK VIGOUR": "Opponent Movement phase reaction after an enemy Normal/Advance/Fall Back move ends: selected EMPEROR'S CHILDREN unit within 9\" (excluding BEASTS/VEHICLES) makes a Normal move up to 6\".",
        "DEVOTED DUELLISTS": "Fight phase: selected EMPEROR'S CHILDREN CHARACTER unit that has not fought gains [SUSTAINED HITS 1] on melee attacks against one selected enemy unit until end of phase.",
        "DIABOLIC MAJESTY": "Shooting/Fight phase reaction when Favoured Champions is updated: selected Favoured Champions EMPEROR'S CHILDREN CHARACTER unit forces enemy units within 6\" to take Battle-shock tests at -1 (once per battle round).",
        "EUPHORIC INSPIRATION": "Charge phase: selected EMPEROR'S CHILDREN DAEMON unit projects a 6\" aura that lets EMPEROR'S CHILDREN units re-roll Charge rolls until end of phase.",
        "HEIGHTENED JEALOUSY": "Shooting/Fight phase reaction when Favoured Champions is updated or destroys an enemy: non-Favoured EMPEROR'S CHILDREN CHARACTER units gain +1 Strength on attacks until end of phase.",
        "HONOUR THE PRINCE": "Movement phase: selected EMPEROR'S CHILDREN INFANTRY unit that has not been selected to move treats its next Advance roll this phase as a fixed +6\".",
        "MUTATION'S CURSE": "Shooting phase: HERETIC ASTARTES PSYKER unit selects one visible enemy within 12\" and deals mortal wounds on a D6 table (1 -> 1, 2-4 -> D3, 5-6 -> 2D3).",
        "NO REST IN DEATH": "Movement phase: HERETIC ASTARTES unit within 9\" of a friendly Psyker/Daemon Prince source either heals one model by D3+1 or, if BATTLELINE, returns up to D3 destroyed non-CHARACTER models.",
        "PRIDEFUL SUPERIORITY": "Fight phase: selected EMPEROR'S CHILDREN unit not yet selected to fight can re-roll Hit and Wound rolls against CHARACTER targets until end of phase.",
        "SHROUD OF CHAOS": "Start of opponent Shooting phase: selected HERETIC ASTARTES Psyker/Daemon Prince source projects a 6\" Stealth aura to friendly HERETIC ASTARTES units until end of phase.",
        "SINUOUS BREACH": "Movement/Charge phase: selected EMPEROR'S CHILDREN DAEMON unit not yet selected to move/charge can move through terrain features this phase for Normal/Advance (Movement phase) or Charge (Charge phase) moves.",
        "SOULSEEKERS": "Shooting phase: selected HERETIC ASTARTES unit that has not been selected to shoot gains [IGNORES COVER] on ranged weapons until end of phase.",
        "UNHOLY HASTE": "Charge phase: selected HERETIC ASTARTES INFANTRY unit that has not attempted a charge can declare a charge after Advancing until end of phase.",
        "REFUSAL TO BE OUTDONE": "Charge phase: selected EMPEROR'S CHILDREN CHARACTER unit gains +2 to Charge rolls against one selected enemy unit that is within Engagement Range of friendly units until end of phase.",
        "VENGEFUL SURGE": "Opponent Shooting phase defensive reaction after enemy targets selected: targeted EMPEROR'S CHILDREN CHARACTER unit can make a reactive Surge move of up to D6\" (reroll if not Favoured Champions) after the attacker finishes shooting.",
        "SUSTAINED BY AGONY": "Fight phase reaction after a friendly EMPEROR'S CHILDREN unit destroys an enemy: select a friendly LEGIONS OF EXCESS unit within 6\" to either heal 3 wounds or, for DAEMONETTES, return D3+3 destroyed models.",
        "SYCOPHANTIC SURGE": "Your Charge phase: selected LEGIONS OF EXCESS unit can charge after Advancing/Falling Back this phase; declared charge targets must include at least one enemy within Engagement Range of a friendly EMPEROR'S CHILDREN unit.",
        "UNCANNY REACTIONS": "Opponent Shooting phase defensive reaction after enemy targets are selected: targeted friendly SLAANESH unit imposes -1 to hit until end of phase.",
        "ECSTATIC SLAUGHTER": "Fight phase reaction after a friendly LEGIONS OF EXCESS unit destroys an enemy: selected EMPEROR'S CHILDREN unit within 6\" and not in Engagement Range attempts an out-of-turn charge.",
        "VIOLENT CRESCENDO": "Fight phase: selected SLAANESH BEASTS/INFANTRY/MOUNTED unit that has not fought gets 6\" pile-in and 6\" consolidate movement overrides until end of phase.",
        "DARK APPARITIONS": "End of opponent Fight phase: selected DAEMONETTES unit not in Engagement Range enters Strategic Reserves and, in your next Movement phase, can Deep Strike at >6\" while arriving wholly within 9\" of a friendly EMPEROR'S CHILDREN unit.",
        "VIOLENT EXCESS": "Fight phase: selected EMPEROR'S CHILDREN unit that has not been selected to fight gains [SUSTAINED HITS 1] on melee weapons until end of phase.",
        "INCESSANT VIOLENCE": "Fight phase: consolidate up to 6\" if the unit can end in Engagement Range.",
        "UNYIELDING FORMS": "Shooting/Fight phase: NECRONS VEHICLE/MOUNTED (non-TITANIC) targeted unit gets -1 to wound if S>T until end of phase.",
        "MERCILESS RECLAMATION": "Shooting/Fight phase: NECRONS (non-TITANIC) unit not yet acted gets +1 to wound vs targets within objective range.",
        "DIMENSIONAL TUNNEL": "Movement phase: NECRONS VEHICLE/MOUNTED (non-TITANIC) can move through models/terrain this phase.",
        "CHRONOSHIFT": "Movement phase: NECRONS VEHICLE/MOUNTED (non-TITANIC) not yet moved treats Advance roll as 6 this phase.",
        "ENDLESS SERVITUDE": "End of Fight phase: NECRONS (non-TITANIC) within controlled objective triggers Reanimation Protocols (D3).",
        "REACTIVE REPOSITION": "Opponent Shooting phase: NECRONS (non-TITANIC) targeted unit makes a Normal move (D6\").",
        "MORDIAN MINUTE": "Shooting phase: ASTRA MILITARUM INFANTRY with First Rank, Fire! Second Rank, Fire! (not yet shot) gains +1 Strength on ranged attacks this phase.",
        "AGGRESSOR IMPERATIVE": "Movement phase: selected SKITARII unit that has not been selected to move treats its Advance distance this phase as a fixed +6\"; if selected unit has BATTLELINE, optionally select one friendly SKITARII unit (excluding BATTLELINE) within 6\" that has not been selected to move to gain the same effect.",
        "BALEFUL HALO": "Fight phase reaction after enemy targets are selected: selected non-VEHICLE ADEPTUS MECHANICUS unit imposes -1 to Wound rolls for attacks that target it this turn; if selected unit has BATTLELINE, optionally select one friendly SKITARII unit (excluding BATTLELINE) within 6\" to gain the same effect.",
        "BULWARK IMPERATIVE": "Opponent Shooting phase reaction after enemy targets are selected: selected SKITARII unit gains a 4+ invulnerable save this phase; if selected unit has BATTLELINE, optionally select one friendly SKITARII unit (excluding BATTLELINE) within 6\" to gain the same effect.",
        "EXTINCTION ORDER": "Command phase: select one TECH-PRIEST model and one objective marker within 24\"; roll one D6 for each enemy unit within range of that marker and on each 4+ that unit suffers 1 mortal wound and takes a Battle-shock test.",
        "LETHAL DOSAGE": "Shooting phase: selected ADEPTUS MECHANICUS unit not yet selected to shoot gains [LETHAL HITS] on ranged weapons this phase; if selected unit has BATTLELINE, optionally select one friendly SKITARII unit (excluding BATTLELINE) within 6\" to gain the same effect.",
        "NO RETREAT!": "Command phase: ASTRA MILITARUM unit with Duty and Honour! selects a controlled objective in range; that objective remains sticky until opponent control breaks it.",
        "PRE-CALIBRATED PURGE SOLUTION": "Shooting phase: selected ADEPTUS MECHANICUS unit not yet selected to shoot re-rolls ranged Hit rolls against enemy units in the opponent deployment zone this phase; if selected unit has BATTLELINE, optionally select one friendly SKITARII unit (excluding BATTLELINE) within 6\" to gain the same effect.",
        "PURGING FIRE": "Shooting phase: ordered ASTRA MILITARUM unit within objective range (not yet shot) gains Lethal Hits on ranged attacks this phase.",
        "SNAP TO IT": "Any phase: ASTRA MILITARUM OFFICER issues one Voice of Command order immediately (local prompt or explicit remote officer/order/target payload).",
        "VETERAN SHARPSHOOTERS": "Shooting phase: ASTRA MILITARUM unit that has not yet shot gains Ignores Cover on ranged attacks this phase.",
        "VOW OF RETRIBUTION": "Shooting phase: IMPERIAL KNIGHTS unit that has not yet shot gains Lethal Hits on ranged attacks until end of phase.",
        "FULL TILT": "Movement phase: IMPERIAL KNIGHTS unit that has not been selected to move gains +2\" Move and +2 to Advance rolls until end of phase.",
        "RUN THEM THROUGH!": "Fight phase: IMPERIAL KNIGHTS unit that has not been selected to fight gains [LANCE] on melee weapons until end of phase.",
        "THUNDERSTOMP": "Fight phase: selected IMPERIAL KNIGHTS model's Armoured/Titanic Feet melee weapons are set to 8/12 Attacks and improve AP by 1 until end of phase.",
        "TACTICAL FOIL": "Opponent Movement phase reaction after an enemy ends a Normal/Advance/Fall Back move: IMPERIAL KNIGHTS unit within 9\" can make a reactive Normal move of up to D6\".",
        "RIGHTEOUS VENGEANCE": "Fight phase: selected ADEPTA SORORITAS unit that has not fought re-rolls melee Hit rolls, and re-rolls melee Wound rolls against Below Half-strength targets, until end of phase.",
        "SUFFERING AND SACRIFICE": "Fight phase start: selected ADEPTA SORORITAS INFANTRY/WALKER forces enemy units in Engagement Range to select it as a Fight target this phase when possible.",
        "SPIRIT OF THE MARTYR": "Opponent Fight phase reaction: targeted ADEPTA SORORITAS unit that has not fought gains fight-on-death sequencing after the attacker finishes its attacks this phase.",
        "PRAISE THE FALLEN": "Opponent Shooting phase reaction after enemy shooting resolves: ADEPTA SORORITAS unit that lost models to that attacker can make a reactive shooting attack into the attacking unit.",
        "SANCTIFIED IMMOLATION": "Any phase reaction before removal: destroyed ADEPTA SORORITAS VEHICLE model with Deadly Demise auto-triggers its explosion.",
        "DIVINE INTERVENTION": "Any phase reaction on destroyed ADEPTA SORORITAS CHARACTER (excluding Saint Celestine): discard 1-3 Miracle dice to return one destroyed model at phase end with D3 + discarded wounds (capped by starting wounds).",
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
        "VECTORED ENGINES": "Your Movement phase reaction after a friendly AELDARI VEHICLE FLY Falls Back: that unit can shoot this turn despite falling back.",
        "ANCESTRAL SENTENCE": "Your Shooting phase: selected LEAGUES OF VOTANN unit not yet selected to shoot gains [SUSTAINED HITS 1] on ranged weapons until end of phase; can optionally spend 3 YP to use [SUSTAINED HITS 2] instead.",
        "HONOUR OF THE HOLD": "Fight phase: selected LEAGUES OF VOTANN unit not yet selected to fight picks one enemy in Engagement Range; until end of phase, melee attacks targeting that enemy gain +1 AP (or +2 AP if 3 YP were spent when using the stratagem).",
        "HUNTR'S MARK": "Your Shooting phase: selected LEAGUES OF VOTANN unit not yet selected to shoot re-rolls Hit rolls of 1 and Wound rolls of 1 on ranged attacks until end of phase.",
        "ORDERED RETREAT": "Your Movement phase reaction after a LEAGUES OF VOTANN unit Falls Back: that unit can shoot and declare a charge this turn despite falling back.",
        "REACTIVE REPRISAL": "Opponent Shooting phase reaction after an enemy unit has shot, while Fortify Takeover is active: selected LEAGUES OF VOTANN unit that was targeted can perform reactive shooting into that attacking unit.",
        "VOID HARDENED": "Opponent Shooting/Fight phase defensive reaction after an enemy unit selects targets, while Fortify Takeover is active: selected LEAGUES OF VOTANN target worsens incoming AP by 1 from that attacker until it finishes its attacks.",
        "UNBRIDLED CARNAGE": "Fight phase: ORKS unit not yet fought scores critical hits on 5+ in melee until end of phase.",
        "ORKS IS NEVER BEATEN": "Fight phase: targeted ORKS unit fights on death after attacker finishes attacks if it has not fought; then removed.",
        "ERE WE GO": "Movement phase start: ORKS INFANTRY unit gains +2 to Advance and Charge rolls until end of turn.",
        "MOB RULE": "Command phase: select ORKS MOB (10+ models, not below half-strength) and a Battle-shocked ORKS INFANTRY within 6\" to clear Battle-shock.",
        "CAREEN!": "On Deadly Demise roll of 6: ORKS VEHICLE moves (Normal/Fall Back) before explosion; can move over enemy units except MONSTER/VEHICLE.",
        "'ARD AS NAILS": "Opponent Shooting/Fight phase: targeted ORKS unit (excluding Grots/Monsters/Vehicles) suffers -1 to wound until end of phase.",
        "\u2019ARD AS NAILS": "Opponent Shooting/Fight phase: targeted ORKS unit (excluding Grots/Monsters/Vehicles) suffers -1 to wound until end of phase.",
        "CORRUPT REALSPACE": "Command phase: corrupt a controlled objective; sticky until opponent controls it at start/end of any turn; 6\" area counts as Shadow of Chaos.",
        "DAEMONIC INVULNERABILITY": "Opponent Shooting phase: targeted LEGIONES DAEMONICA unit re-rolls invulnerable saves of 1 until end of phase.",
        "DELIRIUM UNMADE": "End of opponent Fight phase: select up to two TZEENTCH LEGIONES DAEMONICA units; if selecting two units or any engaged unit, spend 1 Flux; units enter Strategic Reserves.",
        "DENIZENS OF THE WARP": "Movement phase: Deep Strike arrival can be set up more than 6\" horizontally from enemies this phase.",
        "DRAUGHT OF TERROR": "Shooting/Fight phase: LEGIONES DAEMONICA unit gains +1 AP and re-rolls Wound rolls vs Battle-shocked targets until end of phase.",
        "FATEBORNE NIGHTMARES": "Movement/Charge phase: TZEENTCH LEGIONES DAEMONICA unit can move through terrain features this phase.",
        "FICKLEFIRE": "Shooting phase: engaged TZEENTCH LEGIONES DAEMONICA unit ignores engagement for ranged attacks; 5+ backlash mortal wounds on destroyed engaged enemy models.",
        "BLOOD BEGETS SKULLS": "Your Charge phase: LEGIONES DAEMONICA KHORNE unit that has not been selected to charge this phase can charge after advancing this phase.",
        "FOOLS' FLIGHT": "Opponent Movement phase reaction after an enemy Falls Back: LEGIONES DAEMONICA KHORNE unit within 6\" can declare an out-of-turn charge targeting only that enemy, with no charge bonus.",
        "FLICKERING REALITY": "Fight phase: after enemy selects targets, roll D6 (optional Flux re-roll); unmodified hit rolls of that value end attacks against the target this phase.",
        "GORE-HUNGRY ONSLAUGHT": "Movement/Charge phase: LEGIONES DAEMONICA KHORNE unit can move through terrain features for move/advance/fall back (Movement phase) or charge (Charge phase).",
        "SKULLS BEGET BLOOD": "Your Shooting phase: LEGIONES DAEMONICA KHORNE INFANTRY/MOUNTED unit (not Fell Back, not in Engagement Range) selects a visible enemy within 8\" that is not in Engagement Range of your units; roll 6D6 and each 4+ inflicts 1 mortal wound.",
        "SHEATHED IN BRASS": "Opponent Shooting phase defensive reaction after targets selected: targeted LEGIONES DAEMONICA KHORNE unit has Save characteristic 3+ until end of phase.",
        "WRATH UNDENIABLE": "Fight phase defensive reaction after enemy targets selected: targeted LEGIONES DAEMONICA KHORNE unit rolls D6 for each model destroyed by melee attacks this phase; on 4+ that model fights on death after attacks resolve.",
        "GORE‑HUNGRY ONSLAUGHT": "Movement/Charge phase: LEGIONES DAEMONICA KHORNE unit can move through terrain features for move/advance/fall back (Movement phase) or charge (Charge phase).",
        "IMPOSSIBLE ECLIPSE": "Any phase: TZEENTCH LEGIONES DAEMONICA MONSTER extends Shadow of Chaos into No Man's Land and/or opponent deployment until end of phase (both costs Flux).",
        "PYROGENESIS": "Shooting/Fight phase: TZEENTCH LEGIONES DAEMONICA unit gains +2S (or spend Flux for +3S and +1 AP) until end of phase.",
        "THE REALM OF CHAOS": "End of opponent turn: up to two Shadow-of-Chaos units (or one other unit) enter Strategic Reserves and return next Movement phase via Deep Strike.",
        "WARP SURGE": "Charge phase: LEGIONES DAEMONICA unit within Shadow of Chaos can charge after advancing this phase.",
        "AEGIS ETERNAL": "Opponent Shooting phase: targeted GREY KNIGHTS INFANTRY gains a 4+ invulnerable save while its models are wholly within Hallowed Ground.",
        "FIRES OF COVENANT": "Opponent Movement phase: targeted GREY KNIGHTS INFANTRY rolls D6 each time an enemy is set up or ends a Normal/Advance/Fall Back move within 6\"; +2 to the roll while wholly within Hallowed Ground; on 4+ that enemy suffers D3 mortal wounds.",
        "FLAMES OF SANCTITY": "End of Fight phase: targeted PURIFIER SQUAD rolls against each enemy unit within 6\" and inflicts D3 mortal wounds on 4+ (adds 1 to each roll if including Castellan Crowe).",
        "HALLOWED BEACON": "Movement Reinforcements step: targeted GREY KNIGHTS INFANTRY (non-TERMINATOR) Deep Strike arrival can be set up more than 6\" horizontally away from enemies, and placement must be wholly within Hallowed Ground.",
        "REPELLING SPHERE": "Opponent Charge phase: targeted GREY KNIGHTS INFANTRY imposes -1 to enemy Charge rolls that include it as a target, or -2 while wholly within Hallowed Ground.",
        "SANCTIFIED KILL ZONE": "Shooting/Fight phase: targeted GREY KNIGHTS unit wholly within Hallowed Ground gains wound re-rolls (re-roll 1s, or full wound re-rolls for PURIFIER SQUAD) until end of phase.",
    }

    # Some stratagem names are reused across detachments and require detachment-specific notes.
    if name_u == "SOULSIGHT" and det_u == "DEVOTED OF YNNEAD":
        return (
            "Implemented",
            "Your Shooting phase: selected YNNARI unit that has not been selected to shoot gains [LETHAL HITS] and [IGNORES COVER] on ranged weapons until end of phase.",
            name_u,
        )

    if name_u in IMPLEMENTED_STRATAGEM_NAMES_CANONICAL:
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
    return ("Not implemented", "Not implemented in engine.", name_u)


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
                    status, notes, _ = _stratagem_support(
                        s.get("name", ""),
                        s.get("description", ""),
                        detachment_name=det_name,
                        stratagem_id=str(s.get("id", "") or ""),
                    )
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
                                _stratagem_note_block(str(s.get("description", "") or ""), status, notes),
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
        logger.info("⚠️ Datasheets with same name but different content detected:")
        for entry in dedupe_conflicts:
            parts = []
            for item in entry.get("entries", []):
                sid = item.get("id", "")
                src = item.get("source", "")
                parts.append(f"{sid} ({src})" if src else sid)
            logger.info(f" - {entry.get('name', '')}: {', '.join(parts)}")

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
                    _stratagem_note_block(str(s.get("description", "") or ""), status, notes),
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
    logger.info(f"Wrote {OUT_PATH}")
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
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
