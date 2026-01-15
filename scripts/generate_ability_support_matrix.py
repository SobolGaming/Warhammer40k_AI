
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
from warhammer40k_ai.classes.army import SUPPORTED_FACTION_IDS
from warhammer40k_ai.classes.stratagems import (
    IMPLEMENTED_STRATAGEM_NAMES,
    defensive_reaction_note,
    parse_defensive_reaction_stratagem,
)
from warhammer40k_ai.classes.enhancement_effects import classify_enhancement_support
from warhammer40k_ai.classes.wargear import parse_alternate_3


ABILITY_SUPPORT_BY_ID: Dict[str, Tuple[str, str]] = {}
ABILITY_SUPPORT_BY_NAME_FACTION: Dict[Tuple[str, str], Tuple[str, str]] = {}
ABILITY_SUPPORT_BY_NAME_FACTION_DS: Dict[Tuple[str, str, str], Tuple[str, str]] = {}
OPTION_SUPPORT_CACHE: Dict[str, Tuple[str, str]] = {}
WARGEAR_KEYWORD_SUPPORT_CACHE: Dict[Tuple[str, Tuple[str, ...]], Tuple[str, str]] = {}


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
        "Quicksilver Grace": ("Supported", "Mercurial Host: reroll Advance rolls for eligible units."),
        "Exquisite Swordsmanship": ("Supported", "Peerless Bladesmen: on charge choose Lethal or Sustained for melee."),
        "Mechanised Murder": ("Supported", "Rapid Evisceration: reroll Hit/Wound rolls of 1 for eligible units."),
        "Daemonic Empowerment": ("Supported", "Carnival of Excess: empowered units gain Sustained Hits."),
        "Pledges to the Dark Prince": ("Supported", "Coterie pledges tracked per round; pact points unlock bonuses."),
        "Internal Rivalries": ("Supported", "Slaanesh's Chosen: ignore negative Move/Advance/Charge; Favoured reroll Wounds."),
        "Sensational Performance": ("Supported", "Court of the Phoenician: optional +1 S/AP on charge."),
        "Master of the Pageant": ("Supported", "Court of the Phoenician: once per round -1 CP stratagem cost."),
        "Relentless Rage": ("Supported", "Berzerker Warband: on charge, melee weapons gain +1A/+2S until end of turn."),
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
        "Warp Rifts": (
            "Supported",
            "Daemonic Incursion: Deep Strike min distance reduced to 6\" when wholly within Shadow of Chaos zones or within 6\" of a matching Greater Daemon/Dark Master aura; cannot bootstrap off the arriving unit.",
        ),
        "Martial Grace": ("Supported", "Warhost: +1 Battle Focus token; Swift as the Wind +1\" move; +1 to D6 Agile Manoeuvre rolls."),
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
        ("AC", "Daughter of the Abyss"): ("Supported", "Feel No Pain 3+ against Psychic attacks and mortal wounds."),
        ("AC", "Daughters of the Abyss"): ("Supported", "Feel No Pain 3+ against Psychic attacks and mortal wounds."),
        ("AC", "Martial Inspiration"): ("Partial", "Advance-and-charge eligibility applied without once-per-battle restriction."),
        ("AC", "Strike from the Skies"): ("Supported", "Shoot and charge after Falling Back."),
        ("AC", "Tactical Perception"): ("Partial", "Fights First applied without leading restriction."),
        ("ADM", "Dynamic Efficiency"): ("Partial", "Charge-after-Advance/Fall Back supported; Desperate Escape rerolls not implemented."),
        ("ADM", "Elevated Strider"): ("Partial", "Shoot-after-Fall-Back/Advance supported; Desperate Escape rerolls not implemented."),
        ("ADM", "Enginseer"): ("Partial", "Lone Operative applied without 3\" Vehicle proximity or leading restriction."),
        ("ADM", "Mechanicus Bodyguard"): ("Partial", "Lone Operative applied without 3\" unit proximity requirement."),
        ("ADM", "Shroudpsalm (Aura)"): ("Partial", "Stealth applied to bearer only; aura not propagated."),
        ("AM", "Alchemyk Counteragents"): ("Supported", "Feel No Pain 6+ against mortal wounds."),
        ("AM", "Desert Riders"): ("Partial", "Shoot and charge after Falling Back; ignores Move/Advance/Charge modifiers not handled."),
        ("AM", "Enginseer"): ("Partial", "Lone Operative applied without 3\" Vehicle proximity requirement."),
        ("AM", "Horsemasters"): ("Supported", "Shoot and charge after Falling Back."),
        ("AM", "Malign Wardings(Psychic)"): ("Partial", "Feel No Pain 4+ against Psychic attacks applied without leading restriction."),
        ("GK", "Indomitable Spirit (Psychic)"): ("Supported", "Shoot and charge after Advance/Fall Back."),
        ("GK", "Retinue"): ("Partial", "Deep Strike granted without leading restriction; Teleport Assault not implemented."),
        ("GK", "Sanctic Hood"): ("Partial", "Feel No Pain 4+ against Psychic attacks applied without leading restriction."),
        ("GK", "Techmarine"): ("Partial", "Lone Operative applied without 3\" Vehicle proximity requirement."),
        ("GK", "Truesilver Aegis (Aura)"): ("Partial", "Feel No Pain 6+ against mortal wounds applies to bearer only; aura not propagated."),
        ("GK", "Untouchable Purity"): ("Partial", "Feel No Pain 4+ against mortal wounds applied without leading restriction."),
        ("AOI", "Abomination"): ("Supported", "Feel No Pain 2+ against Psychic attacks."),
        ("AOI", "Backroom Deals"): ("Partial", "Infiltrators applied without formation selection/leading restriction."),
        ("AOI", "Frenzon"): ("Supported", "Shoot and charge after Advancing."),
        ("AOI", "Psychic Hood"): ("Supported", "Feel No Pain 4+ against Psychic attacks."),
        ("AOI", "Rites of Teleportation"): ("Partial", "Deep Strike granted without Inquisitor attachment restriction."),
        ("AOI", "Unsubtle Crusader"): ("Partial", "Scouts 6\" applied without formation selection/target-unit restriction."),
        ("AE", "ASPECT TRAINING"): ("Partial", "Fights First/Infiltrators/Scouts/Stealth detected; leader/unit restrictions not enforced."),
        ("AE", "Aspect Shrine Token"): (
            "Supported",
            "Per-roll prompt lets non-CHARACTER models change a hit or wound roll to an unmodified 6, consuming a token; tokens tracked from wargear options with per-activation prompt suppression.",
        ),
        ("AE", "Way of the Blade"): ("Partial", "Fights First applied without leader restriction."),
        ("AE", "Empowered by Death"): ("Partial", "Fights First applied without below-strength condition."),
        ("AE", "Spiritseer"): ("Partial", "Lone Operative applied without 3\" Wraith Construct proximity requirement."),
        ("AE", "Bonesinger"): ("Partial", "Lone Operative applied without 3\" proximity/leading restrictions."),
        ("AE", "Superlative Strategist"): ("Partial", "Advance reroll enabled; leading/Agile Manoeuvre rerolls not enforced."),
        ("AE", "Acrobatic"): ("Supported", "Charge-after-Advance/Fall Back eligibility."),
        ("AE", "Blur of Movement"): ("Supported", "Charge-after-Advance eligibility."),
        ("AE", "War Construct"): ("Supported", "Shoot after Falling Back."),
        ("AE", "Flawless Poise"): ("Supported", "Shoot and charge after Falling Back."),
        ("AE", "Into the Foe"): ("Partial", "Charge-after-Advance applies to the transport; disembark timing/target unit requirement not enforced."),
        ("CD", "Bounding Leaps"): ("Supported", "Shoot after Falling Back."),
        ("CD", "Chosen Marauders"): ("Supported", "Shoot and charge after Advance/Fall Back."),
        ("CD", "Brass Collar of Bloody Vengeance"): ("Supported", "Feel No Pain 3+ against Psychic attacks and mortal wounds."),
        ("CD", "Daemonic Lord"): ("Partial", "Lone Operative applied without 3\" Legiones Daemonica Infantry proximity requirement."),
        ("CD", "Daemon Lord of Khorne (Aura)"): ("Supported", "+1 to hit (melee) aura within 6\" for KHORNE LEGIONES DAEMONICA."),
        ("CD", "Shadow Form"): ("Supported", "Shadow Form selection each battle round with active effect tracking."),
        ("CD", "Wreathed in Shadows (Aura, Psychic)"): ("Supported", "18\" ranged targeting restriction while within 6\" of active Shadow Form source."),
        ("CD", "Pall of Despair (Aura, Psychic)"): ("Supported", "Forces Battle-shock tests for Below Starting Strength units within 9\" in opponent Command phase; heals on failed tests."),
        ("CD", "Shadow Lord (Aura, Psychic)"): ("Supported", "Re-roll Hit rolls of 1 aura within 6\" while active."),
        ("CD", "The Dark Master (Aura)"): ("Supported", "Area within 6\" counts as Shadow of Chaos."),
        ("CD", "Monarch of the Hunt"): ("Supported", "Quarry selection + melee reroll hooks vs quarry."),
        ("CD", "No Prey Can Evade"): ("Supported", "Re-roll Advance and Charge rolls."),
        ("CD", "Unholy Speed"): ("Supported", "Re-roll Advance and Charge rolls."),
        ("CD", "Pack Leader"): ("Supported", "Leading: re-roll Advance and Charge rolls for the unit."),
        ("CSM", "Warpsmith"): ("Partial", "Lone Operative applied without 3\" Heretic Astartes Vehicle proximity requirement."),
        ("CSM", "Indentured Daemon Engines"): ("Partial", "Lone Operative applied without 3\" Daemon Vehicle proximity requirement."),
        ("CSM", "Chosen Marauders"): ("Supported", "Shoot and charge after Advance/Fall Back."),
        ("CSM", "Hovering Death"): ("Supported", "Shoot and charge after Falling Back."),
        ("EC", "Daemonic Speed"): ("Supported", "Fights First."),
        ("EC", "Duellist's Hubris"): ("Supported", "Fights First when not leading a unit."),
        ("EC", "Lord of Excess"): ("Partial", "Lone Operative applied without 3\" Slaanesh Infantry proximity requirement."),
        ("EC", "LORD OF THE HOST"): ("Partial", "Infiltrators/Scouts 6\" detected; attachment restriction not enforced."),
        ("EC", "Lethal Obsession"): ("Partial", "Charge reroll always available; requires prior same-target shooting not enforced."),
        ("EC", "No Prey Can Evade"): ("Supported", "Re-roll Advance and Charge rolls."),
        ("EC", "Unholy Speed"): ("Supported", "Re-roll Advance and Charge rolls."),
        ("EC", "Monarch of the Hunt"): ("Supported", "Quarry selection + melee reroll hooks vs quarry."),
        ("DG", "Death Guard Defenders"): ("Partial", "Lone Operative applied without 3\" Death Guard Infantry proximity requirement."),
        ("DG", "Hovering Death"): ("Supported", "Shoot and charge after Falling Back."),
        ("DG", "Blinding Spray"): ("Partial", "Fights First applied without selection/once-per-battle restriction."),
        ("DRU", "ARCHON'S RETINUE"): ("Partial", "Scouts 7\" applied without leader/attachment restriction (affects unit)."),
        ("DRU", "Blur of Blades"): ("Partial", "Fights First applied without leading restriction."),
        ("DRU", "Blur of Movement"): ("Supported", "Charge-after-Advance eligibility."),
        ("GC", "Sudden Assault"): ("Partial", "Fights First applied without leading restriction."),
        ("GC", "Swift and Deadly"): ("Supported", "Charge-after-Advance eligibility."),
        ("LOV", "Brōkhyr Guild Support"): ("Partial", "Lone Operative applied without 3\" Vehicle/Ironkin proximity or attached-unit restriction."),
        ("LOV", "Science Guild Support"): ("Partial", "Lone Operative applied without 3\" Infantry proximity or exclusion of Lone Operative units."),
        ("LOV", "Teleport Crest"): ("Partial", "Deep Strike granted; leading restriction not enforced where applicable."),
        ("NEC", "Adaptive Strategy"): ("Supported", "Shoot and charge after Falling Back."),
        ("NEC", "Ghostwalk Mantle"): ("Partial", "Fights First applied without leading restriction."),
        ("NEC", "Illuminor"): ("Partial", "Lone Operative applied without 3\" proximity to friendly Necrons."),
        ("NEC", "Protective Disciples"): ("Partial", "Lone Operative applied without 3\" proximity to Destroyer Cult units."),
        ("NEC", "VANGUARD PROTOCOLS"): ("Partial", "Scouts 8\" applied without attached-unit restriction."),
        ("NEC", "Relentless Combatants"): ("Supported", "Re-roll Charge rolls. Charge-after-Fall-Back eligibility."),
        ("NEC", "Shadowloom"): ("Supported", "Stealth."),
        ("NEC", "Gloom Prism (Aura)"): ("Partial", "Feel No Pain vs Psychic (and mortal where listed) applies to bearer only; aura not propagated."),
        ("NEC", "Nullstone Field Generator (Aura)"): ("Partial", "Feel No Pain vs mortal/psychic applies to bearer only; aura not propagated."),
        ("ORK", "Full Throttle"): ("Supported", "Charge-after-Advance and charge-after-Fall-Back eligibility."),
        ("ORK", "Mekboy"): ("Partial", "Lone Operative applied without 3\" Vehicle proximity requirement."),
        ("ORK", "Super Runts"): ("Partial", "Scouts 9\" applied without leading restriction; hit/wound bonus not implemented."),
        ("ORK", "Tellyporta Tech"): ("Partial", "Deep Strike granted without leading restriction."),
        ("ORK", "Drill Boss"): ("Supported", "Leading: +1 to hit for melee attacks in the unit."),
        ("TAU", "Advanced Armour"): ("Supported", "Feel No Pain 4+ against mortal wounds."),
        ("TAU", "Agile Combatant"): ("Supported", "Shoot after Falling Back."),
        ("TAU", "Recon Drone"): ("Supported", "Infiltrators."),
        ("TYR", "Adaptable Predators"): ("Supported", "Shoot and charge after Falling Back."),
        ("TYR", "Bounding Leap"): ("Supported", "Charge-after-Advance eligibility."),
        ("TYR", "Irresistible Force"): ("Supported", "Charge-after-Fall-Back eligibility."),
        ("TYR", "Foul Spores (Aura)"): ("Partial", "Stealth applied to bearer only; aura cover/stealth to nearby units not implemented."),
        ("TYR", "Unnatural Resilience"): ("Supported", "Feel No Pain 4+ against mortal wounds."),
        ("TS", "Bounding Leaps"): ("Supported", "Shoot after Falling Back."),
        ("TS", "Servile Pawns"): ("Partial", "Lone Operative applied without 3\" Thousand Sons Infantry proximity requirement."),
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
        ("SM", "Tempormortis"): ("Supported", "Fights First while leading a unit."),
        ("SM", "Pack Leader"): ("Supported", "Unit cannot be your Warlord or be given Enhancements."),
    }
    out: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for (fid, name), val in raw.items():
        out[(str(fid or "").strip().upper(), _norm(name))] = val
    return out


def _datasheet_ability_support_by_name_faction_datasheet() -> Dict[Tuple[str, str, str], Tuple[str, str]]:
    raw = {
        ("WE", "Frenzy", "000002632"): ("Supported", "After being targeted, Helbrute can shoot or fight vs the attacker (eligible target check)."),
        ("WE", "Furious Onslaught", "000002638"): ("Supported", "Ranged attacks vs closest eligible target within 18\" allow an optional Hit re-roll."),
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


def _classify_ability(
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
    chapter_restriction_support = None
    if description:
        if "RESTRICTIONS" not in description.upper():
            chapter_restriction_support = _space_marine_chapter_restriction_support(description)
    else:
        chapter_restriction_support = _space_marine_chapter_restriction_support(name)
    if desc_support:
        return desc_support
    if chapter_restriction_support:
        return chapter_restriction_support
    closest_m_veh_support = _closest_monster_vehicle_reroll_support(description)
    unit_contains_oc_support = _unit_contains_oc_support(description)
    aura_oc_support = _aura_objective_control_support(description)
    aura_adv_charge_support = _aura_advance_charge_roll_support(description)
    fall_back_shoot_support = _fall_back_shoot_support(description)
    charge_move_devastating_support = _charge_move_devastating_wounds_support(description)
    phase_move_support = _leading_unit_phase_move_support(description)
    common_support = _bearer_unit_common_support(description)
    leading_support = _leading_unit_common_support(description)
    bearer_invuln_support = _bearer_invulnerable_save_support(description)
    bearer_smoke_support = _bearer_smoke_keyword_support(description)
    unit_hit_reroll_support = _unit_hit_reroll_ones_support(description)
    unit_wound_reroll_support = _unit_wound_reroll_ones_support(description)
    target_hit_penalty_support = _target_hit_roll_penalty_support(description)
    melee_damage_support = _melee_damage_bonus_support(description)
    two_melee_weapons_support = _two_melee_weapons_bonus_support(description)
    attached_possessed_support = _attached_possessed_formation_bonus_support(description)
    transport_support = _transport_disembark_support(description)
    sticky_support = _sticky_objective_support(description)
    bodyguard_return_support = _command_phase_bodyguard_return_support(description)
    opponent_turn_reserves_support = _opponent_turn_strategic_reserves_support(description)
    enemy_fall_back_desperate_escape_support = _enemy_fall_back_desperate_escape_support(description)
    command_phase_bonus_cp_support = _command_phase_bonus_cp_support(description)
    command_phase_regain_wound_support = _command_phase_regain_wound_support(description)
    reinforcements_denial_support = _reinforcements_denial_support(description)
    cp_on_destroy_support = _gain_cp_on_destroy_support(description)
    battlesuit_support_system_support = _battlesuit_support_system_support(name, description)
    attack_roll_rule_support = _attack_roll_rule_support(description)
    closest_enemy_hit_charge_support = _closest_enemy_hit_and_charge_reroll_support(description)
    orders_support = _orders_section_support(name, description)
    attached_unit_support = _attached_unit_support(name, description)
    model_reroll_support = _model_reroll_wound_vs_character_support(description)
    attack_roll_cp_support = _attack_roll_plus_cp_on_destroy_support(description)
    model_hit_vs_fly_support = _model_hit_bonus_vs_fly_support(description)
    targeted_stratagem_discount_support = _targeted_stratagem_cp_discount_support(description)
    charge_end_mortal_support = _charge_end_mortal_wounds_support(description)
    fight_within_3_support = _fight_within_3_support(description)
    allocated_damage_reduction_support = _allocated_damage_reduction_support(description)

    if battlesuit_support_system_support:
        return battlesuit_support_system_support

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
    if unit_contains_oc_support:
        return unit_contains_oc_support
    if aura_oc_support:
        return aura_oc_support
    if aura_adv_charge_support:
        return aura_adv_charge_support
    if fall_back_shoot_support:
        return fall_back_shoot_support
    if charge_move_devastating_support:
        return charge_move_devastating_support
    if phase_move_support:
        return phase_move_support
    if common_support and leading_support:
        if common_support[0] == "Supported" and leading_support[0] == "Supported":
            notes = " ".join([common_support[1], leading_support[1]]).strip()
            return ("Supported", notes)
        return common_support
    if common_support:
        return common_support
    if leading_support:
        return leading_support
    if bearer_invuln_support:
        return bearer_invuln_support
    if bearer_smoke_support:
        return bearer_smoke_support
    if unit_hit_reroll_support:
        return unit_hit_reroll_support
    if unit_wound_reroll_support:
        return unit_wound_reroll_support
    if target_hit_penalty_support:
        return target_hit_penalty_support
    if melee_damage_support:
        return melee_damage_support
    if two_melee_weapons_support:
        return two_melee_weapons_support
    if attached_possessed_support:
        return attached_possessed_support
    if transport_support:
        return transport_support
    if sticky_support:
        return sticky_support
    if bodyguard_return_support:
        return bodyguard_return_support
    if opponent_turn_reserves_support:
        return opponent_turn_reserves_support
    if enemy_fall_back_desperate_escape_support:
        return enemy_fall_back_desperate_escape_support
    if command_phase_bonus_cp_support:
        return command_phase_bonus_cp_support
    if command_phase_regain_wound_support:
        return command_phase_regain_wound_support
    if reinforcements_denial_support:
        return reinforcements_denial_support
    if cp_on_destroy_support:
        return cp_on_destroy_support
    if attack_roll_rule_support:
        return attack_roll_rule_support
    if closest_enemy_hit_charge_support:
        return closest_enemy_hit_charge_support
    if orders_support:
        return orders_support
    if attached_unit_support:
        return attached_unit_support
    if model_reroll_support:
        return model_reroll_support
    if attack_roll_cp_support:
        return attack_roll_cp_support
    if model_hit_vs_fly_support:
        return model_hit_vs_fly_support
    if targeted_stratagem_discount_support:
        return targeted_stratagem_discount_support
    if charge_end_mortal_support:
        return charge_end_mortal_support
    if fight_within_3_support:
        return fight_within_3_support
    if allocated_damage_reduction_support:
        return allocated_damage_reduction_support
    return ("Not implemented", "")


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


def _bearer_unit_common_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    text = _strip_html(description)
    text = text.replace("\u2019", "'").replace("\u0192?T", "'")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    low = text.lower()
    notes: List[str] = []
    leading_prefix = ""
    if "while this model is leading a unit" in low:
        leading_prefix = "Leading: "

    m = re.search(
        r"add\s+(\d+)\s+to\s+charge\s+rolls?\s+made\s+for\s+the\s+bearer'?s\s+unit",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        notes.append(f"Charge rolls for bearer's unit get +{m.group(1)}.")

    m = re.search(
        r"add\s+(\d+)\s+to\s+advance\s+and\s+charge\s+rolls?\s+made\s+for\s+the\s+bearer'?s\s+unit",
        low,
        flags=re.IGNORECASE,
    )
    if m:
        if leading_prefix:
            notes.append(f"{leading_prefix}Advance and Charge rolls for the unit +{m.group(1)}.")
        else:
            notes.append(f"Advance and Charge rolls for bearer's unit +{m.group(1)}.")
    else:
        m = re.search(
            r"add\s+(\d+)\s+to\s+advance\s+rolls?\s+made\s+for\s+the\s+bearer'?s\s+unit",
            low,
            flags=re.IGNORECASE,
        )
        if m:
            if leading_prefix:
                notes.append(f"{leading_prefix}Advance rolls for the unit +{m.group(1)}.")
            else:
                notes.append(f"Advance rolls for bearer's unit +{m.group(1)}.")

    advance_charge_re = re.search(r"re-?roll\s+advance\s+and\s+charge\s+rolls?", low, flags=re.IGNORECASE)
    if advance_charge_re:
        if "bearer's unit" in low or "that unit" in low:
            notes.append("Re-roll Advance and Charge rolls for bearer's unit.")
        elif leading_prefix:
            notes.append("Leading: re-roll Advance and Charge rolls for the unit.")
        else:
            notes.append("Re-roll Advance and Charge rolls.")

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
        r"models?\s+in\s+the\s+bearer'?s\s+unit\s+have\s+(?:a\s+|the\s+)?feel\s+no\s+pain\s*([1-6])\+?(?:\s+ability)?",
        low,
        flags=re.IGNORECASE,
    )
    if not m and leading_prefix:
        m = re.search(
            r"models?\s+in\s+that\s+unit\s+have\s+(?:a\s+|the\s+)?feel\s+no\s+pain\s*([1-6])\+?(?:\s+ability)?",
            low,
            flags=re.IGNORECASE,
        )
    if m:
        if leading_prefix:
            notes.append(f"{leading_prefix}Feel No Pain {m.group(1)}+.")
        else:
            notes.append(f"Bearer's unit gains Feel No Pain {m.group(1)}+.")

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
        rf"{lead_prefix}add \d+ to advance rolls made for {unit_ref}",
        rf"{lead_prefix}(?:you can |can )?reroll advance and charge rolls made for (?:this model|{unit_ref})",
        rf"{lead_prefix}(?:you can |can )?reroll charge rolls made for (?:this model|{unit_ref})",
        rf"{lead_prefix}bearers unit declares a charge .* objective marker .* reroll the charge roll",
        rf"{lead_prefix}reroll charge rolls .* set up on the battlefield",
        rf"{lead_prefix}models in {unit_ref} have a leadership characteristic of \d+",
        rf"{lead_prefix}add \d+ to the objective control characteristic of (?:models in )?{unit_ref}",
        rf"{lead_prefix}models? in {unit_ref} have (?:a|the)? feel no pain [1-6](?: ability)?",
        rf"{lead_prefix}models? in {unit_ref} have (?:a|the)? feel no pain [1-6](?: ability)? against psychic attacks",
        rf"{lead_prefix}models? in {unit_ref} have (?:a|the)? feel no pain [1-6](?: ability)? against psychic attacks and mortal wounds?",
        rf"{lead_prefix}models? in {unit_ref} have (?:a|the)? feel no pain [1-6](?: ability)? against mortal wounds?",
        rf"{lead_prefix}models? in {unit_ref} have (?:a|the)? feel no pain [1-6](?: ability)? against mortal wounds? and psychic attacks",
        rf"{lead_prefix}(?:melee |ranged )?weapons equipped by models in {unit_ref} have the sustained hits \d+ ability",
        rf"{lead_prefix}(?:melee |ranged )?(?:weapons equipped by models in|attacks made by models in) {unit_ref} .* ignores cover(?: ability)?",
        rf"{lead_prefix}each time (?:a|an) (?:melee |ranged )?attack targets {unit_ref} subtract 1 from the hit roll",
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


def _bearer_smoke_keyword_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    if not re.fullmatch(r"(?:the )?bearer has the smoke keyword", norm):
        return None
    return ("Supported", "Bearer gains the SMOKE keyword.")


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


def _model_reroll_wound_vs_character_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    reroll_pattern = (
        r"each time this model makes (?:a|an)?(?: melee| ranged)? attacks? that targets a character (?:unit|model) "
        r"you can reroll the (?:hit|wound) roll(?:s)?(?: and you can reroll the (?:hit|wound) roll(?:s)?)?"
    )
    cp_pattern = (
        r"each time (?:this model|this models unit|this unit) destroys an? (?:enemy )?character (?:model|unit) you gain \d+ ?cp"
    )
    sentences = [s for s in (_norm_rules_text(part) for part in re.split(r"[.;]\s*", _strip_html(description))) if s]
    unsupported = [s for s in sentences if not (re.fullmatch(reroll_pattern, s) or re.fullmatch(cp_pattern, s))]
    if unsupported:
        return None
    hit_reroll = "reroll the hit roll" in norm and "hit roll of 1" not in norm
    wound_reroll = "reroll the wound roll" in norm and "wound roll of 1" not in norm
    if not (hit_reroll or wound_reroll):
        return None
    cp_on_kill = bool(re.search(r"gain \d+ ?cp", norm) and "destroy" in norm and "character" in norm)
    notes = []
    if hit_reroll:
        notes.append("Model attacks vs CHARACTER units can re-roll the Hit roll (optional).")
    if wound_reroll:
        notes.append("Model attacks vs CHARACTER units can re-roll the Wound roll (optional).")
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
    return None


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
    if "within" in norm:
        return None
    pattern = (
        r"once per battle round one (?:unit|model) from your army with this ability can use it when "
        r"(?:its unit|this models unit|that models unit) is targeted with a stratagem reduce the cp cost of that "
        r"(?:use|usage) of that stratagem by 1cp"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "Once per battle round, when this unit is targeted with a Stratagem, you can reduce its CP cost by 1.",
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
    if "leading a unit" not in low:
        return None
    if "model in that unit" not in low and "models in that unit" not in low:
        return None
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

    lead_prefix = r"(?:while this model is leading a unit )?"
    patterns = [
        rf"{lead_prefix}melee weapons equipped by models in that unit have the lethal hits ability",
        rf"{lead_prefix}ranged weapons equipped by models in that unit have the lethal hits ability",
        rf"{lead_prefix}weapons equipped by models in that unit have the lethal hits ability",
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
    unsupported = [s for s in sentences if s not in base_sentences and not objective_clause_re.match(s.lower())]

    if objective_sentences:
        notes.append("If the target is within range of an objective marker, the Hit roll can be re-rolled instead (optional).")

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
    objective_sentences = [s for s in sentences if objective_clause_re.match(s.lower())]
    unsupported = [s for s in sentences if s not in base_sentences and not objective_clause_re.match(s.lower())]

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

    unit_re = re.compile(
        r"^each time (?:a|an) (?:(?P<atype>melee|ranged) )?attack targets this unit, subtract 1 from the hit roll(?P<tail>.*)$",
        re.IGNORECASE,
    )
    model_re = re.compile(
        r"^each time (?:a|an) (?:(?P<atype>melee|ranged) )?attack targets this model, subtract 1 from the hit roll(?P<tail>.*)$",
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
    loc = (
        r"at the end of your command phase if this unit is within range of an objective marker you control "
        r"that objective marker remains under your control until your opponents level of control over that "
        r"objective marker is greater than yours at the end of a phase"
    )
    if not (re.fullmatch(legacy, norm) or re.fullmatch(legacy_timed, norm) or re.fullmatch(loc, norm)):
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


def _opponent_turn_strategic_reserves_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    pattern = (
        r"at the end of your opponents turn if this unit is not within engagement range of one or more enemy units "
        r"you can remove it from the battlefield and place it into strategic reserves"
    )
    if not re.fullmatch(pattern, norm):
        return None
    return (
        "Supported",
        "End of opponent's turn: if not in Engagement Range, may enter Strategic Reserves.",
    )


def _enemy_fall_back_desperate_escape_support(description: str) -> Optional[Tuple[str, str]]:
    if not description:
        return None
    norm = _norm_rules_text(description)
    if not norm:
        return None
    base = (
        r"each time an enemy unit(?: excluding monsters and vehicles)? within engagement range of one or more units from your army with this ability falls back "
        r"models in that enemy unit must take desperate escape tests?"
    )
    penalty_clause = r"(?: when doing so if that enemy unit is also battle shocked subtract (?P<pen>\d+) from each of those desperate escape tests)?"
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
        "000010078002": "Icon of War: BLOOD LEGIONS within 6\" gain Blessings of Khorne; with Might of Khorne active, may re-roll Battle-shock tests.",
        "000010078003": "Blood-forged Armour: set bearer Save to 2+; gain 1 Blood Tithe point when bearer is destroyed.",
        "000010078004": "Disciple of Khorne: Lord on Juggernaut can attach to Bloodcrushers/Flesh Hounds; bearer gains Deep Strike and BLOOD LEGIONS (instead of WORLD EATERS) while leading; attached unit benefits from Blessings of Khorne (FAQ).",
        "000010078005": "Blade of Endless Bloodshed: +1 A/S/D for bearer melee weapons; melee kill auto-grants 1 Blood Tithe point.",
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
        "ARMOUR OF CONTEMPT": "Shooting/Fight phase: targeted ADEPTUS ASTARTES unit worsens AP by 1 vs the attacking unit until it finishes its attacks.",
        "BERZERKER'S WRATH": "Blood Surge distance is fixed at 8\" (no D6 roll) for a BERZERKERS unit.",
        "BERZERKER’S WRATH": "Blood Surge distance is fixed at 8\" (no D6 roll) for a BERZERKERS unit.",
        "BLESSING OF BURNING BLOOD": "Shooting/Fight phase: after enemy targets; BLOOD LEGIONS unit within 6\" of targeted WORLD EATERS grants 5++ (4++ if Boon of Blood active) until end of phase.",
        "BLITZING FIREPOWER": "Shooting phase: ASURYANI unit gains Sustained Hits 1 vs targets within 12\"; if already has Sustained Hits, crits on 5+.",
        "FEIGNED RETREAT": "Movement phase: ASURYANI unit that Fell Back can shoot and charge this turn.",
        "FIRE AND FADE": "Shooting phase: ASURYANI INFANTRY makes Normal move D6+1\" after shooting; cannot charge or embark this turn.",
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
    }

    if name_u in IMPLEMENTED_STRATAGEM_NAMES:
        return ("Implemented", notes.get(name_u, "Implemented in engine."), name_u)
    spec = parse_defensive_reaction_stratagem(name, description or "")
    if spec:
        return ("Implemented", defensive_reaction_note(spec), name_u)
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
        status = _summary_status(supported, total)
        summary_rows.append(
            (
                [
                    _escape(faction_name),
                    _escape(_summary_icon(supported, total)),
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
