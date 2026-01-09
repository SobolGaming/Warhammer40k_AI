
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

SRC_DIR = os.path.join(ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from warhammer40k_ai.utility.faction_rule_metadata import FACTION_RULE_METADATA
from warhammer40k_ai.classes.army import SUPPORTED_FACTION_IDS
from warhammer40k_ai.classes.stratagems import IMPLEMENTED_STRATAGEM_NAMES
from warhammer40k_ai.classes.enhancement_effects import classify_enhancement_support


STATUS_COLORS = {
    "supported": "#e6f4ea",
    "implemented": "#e6f4ea",
    "partial": "#fff4cc",
    "not implemented": "#fdecea",
}


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _norm(text: str) -> str:
    t = str(text or "").lower()
    t = t.replace("\u2019", "'")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = text.replace("\u2019", "'")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _ascii_text(text: str) -> str:
    t = str(text or "")
    t = t.replace("\u2019", "'").replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
    t = t.encode("ascii", "ignore").decode("ascii")
    return t


def _escape(text: str) -> str:
    return html.escape(_ascii_text(text), quote=True)


def _status_color(status: str) -> str:
    key = _norm(status)
    return STATUS_COLORS.get(key, "#fdecea")

def _status_icon(status: str) -> str:
    key = _norm(status)
    if key in ("supported", "implemented"):
        return ":green_square:"
    if key == "partial":
        return ":yellow_square:"
    return ":red_square:"


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
    body = f"<strong>Engine:</strong> {engine}"
    return _details("Description", body)

def _ability_support_overrides() -> Dict[str, Tuple[str, str]]:
    return {
        "acts of faith": ("Supported", "Miracle dice pool with per-phase Act usage and substitution tracking."),
        "martial ka tah": ("Supported", "Fight-phase Ka'tah selection with Lethal/Sustained hit hooks."),
        "doctrina imperatives": ("Supported", "Round-based imperatives with WS/BS/AP/heavy/assault modifiers."),
        "voice of command": ("Supported", "Order issuing in Command phase with stat modifiers."),
        "gate of infinity": ("Supported", "Teleport eligible units with placement validation."),
        "assigned agents": ("Supported", "Imperial Agents ally caps enforced by battle size."),
        "code chivalric": ("Supported", "Deed/Quality tracking with on-roll effects."),
        "bondsman": ("Supported", "Bondsman buffs applied to Armiger units."),
        "super heavy walker": ("Partial", "Terrain traversal handling only."),
        "freeblades": ("Supported", "Imperial Knights ally and detachment restrictions enforced."),
        "battle focus": ("Supported", "Token system + maneuver selection with per-phase limits."),
        "disparate paths": ("Supported", "Harlequin/Ynnari ally validation in mustering."),
        "power from pain": ("Partial", "Pain token engine with partial ability coverage."),
        "corsairs and travelling players": ("Supported", "Corsairs/Travelling Players ally limits enforced."),
        "cult ambush": ("Supported", "Resurgence points, ambush markers, reinforcements."),
        "prioritised efficiency": ("Supported", "Yield points + mode tracking with objective checks."),
        "reanimation protocols": ("Supported", "Command-phase reanimation sequencing for Necrons."),
        "waaagh": ("Supported", "Once-per-battle Waaagh effects tracked and applied."),
        "for the greater good": ("Supported", "Observer/Guided targeting with markerlight bonuses."),
        "synapse": ("Supported", "Synapse aura checks via distance rules."),
        "shadow in the warp": ("Supported", "Once-per-battle armywide Battle-shock trigger."),
        "the shadow of chaos": ("Supported", "Shadow zones + manifestations/terror handling."),
        "daemonic pact": ("Supported", "Chaos Daemon ally validation with caps and keyword rules."),
        "harbingers of dread": ("Supported", "Dread ability selection and aura checks."),
        "dreadblades": ("Supported", "Chaos Knights ally validation and model caps."),
        "dark pacts": ("Supported", "Dark Pacts selection with lethal/sustained hooks."),
        "cult of the dark gods": ("Supported", "Cult ally points caps and keyword adjustments."),
        "nurgle s gift aura": ("Supported", "Contagion range + plague effects."),
        "pact of decay": ("Supported", "Army faction restriction enforced during validation."),
        "thrill seekers": ("Supported", "EC core rule hooks for crits and movement bonuses."),
        "pact of excess": ("Supported", "Army faction restriction enforced during validation."),
        "cabal of sorcerers": ("Supported", "Cabal rituals and warp charge checks."),
        "pact of sorcery": ("Supported", "Army faction restriction enforced during validation."),
        "blessings of khorne": ("Supported", "Blessings dice engine + effects."),
        "pact of blood": ("Supported", "Army faction restriction enforced during validation."),
        "oath of moment": ("Supported", "Target selection + hit/wound bonuses."),
        "templar vows": ("Supported", "Vow selection with combat/objective effects."),
        "space marine chapters": ("Supported", "Chapter keyword restrictions and unit bans."),
        "deathwatch": ("Supported", "Deathwatch-only chapter restrictions."),
        "leader": ("Supported", "Attach Leaders during battle formations; protect Characters until Bodyguard is gone."),
        "deep strike": ("Supported", "Reserves placement in Reinforcements step; enforces >9\" distance."),
        "feel no pain": ("Supported", "Post-damage roll to ignore wounds, including mortals."),
        "fights first": ("Supported", "Fight phase sequencing uses Fights First step."),
        "fight on death": ("Supported", "Destroyed units can fight after attacker resolves."),
        "shoot on death": ("Supported", "Destroyed units can shoot after attacker resolves."),
        "firing deck": ("Supported", "Transports fire with selected embarked weapons; marks passengers as shot."),
        "infiltrators": ("Supported", "Forward deploy placement >9\" from enemy zone/models."),
        "lone operative": ("Supported", "Ranged targeting blocked beyond 12\" when not Attached."),
        "scouts": ("Supported", "Pre-game Scout move, including transport use when applicable."),
        "stealth": ("Supported", "Apply -1 to hit vs ranged attacks."),
        "deadly demise": ("Supported", "On destruction, roll 6+ to deal mortals within 6\"."),
        "hover": ("Not implemented", "No hover-specific handling."),
        "quicksilver grace": ("Supported", "Mercurial Host: reroll Advance rolls for eligible units."),
        "exquisite swordsmanship": ("Supported", "Peerless Bladesmen: on charge choose Lethal or Sustained for melee."),
        "mechanised murder": ("Supported", "Rapid Evisceration: reroll Hit/Wound rolls of 1 for eligible units."),
        "daemonic empowerment": ("Supported", "Carnival of Excess: empowered units gain Sustained Hits."),
        "pledges to the dark prince": ("Supported", "Coterie pledges tracked per round; pact points unlock bonuses."),
        "internal rivalries": ("Supported", "Slaanesh's Chosen: ignore negative Move/Advance/Charge; Favoured reroll Wounds."),
        "sensational performance": ("Supported", "Court of the Phoenician: optional +1 S/AP on charge."),
        "master of the pageant": ("Supported", "Court of the Phoenician: once per round -1 CP stratagem cost."),
    }


def _ability_patterns() -> List[Tuple[str, str, str]]:
    return [
        ("Deep Strike", "Supported", r"\bdeep strike\b"),
        ("Infiltrators", "Supported", r"\binfiltrator"),
        ("Scouts", "Supported", r"\bscouts?\b"),
        ("Stealth", "Supported", r"\bstealth\b"),
        ("Lone Operative", "Supported", r"\blone operative\b"),
        ("Deadly Demise", "Supported", r"\bdeadly demise\b"),
        ("Feel No Pain", "Supported", r"\bfeel no pain\b"),
        ("Fights First", "Supported", r"\bfights first\b"),
        ("Fight on Death", "Supported", r"\bfight(s)? on death\b"),
        ("Shoot on Death", "Supported", r"\bshoot(s)? on death\b"),
        ("Advance+Shoot", "Supported", r"\beligible to shoot\b.*\badvance(d)?\b"),
        ("Fall Back+Shoot", "Supported", r"\beligible to shoot\b.*\bfell back\b"),
        ("Advance+Charge", "Supported", r"\beligible to declare a charge\b.*\badvance(d)?\b"),
        ("Firing Deck", "Supported", r"\bfiring deck\b"),
        ("Plunging Fire", "Supported", r"\bplunging fire\b"),
    ]


def _classify_ability(name: str, description: str) -> Tuple[str, str]:
    overrides = _ability_support_overrides()
    key = _norm(name)
    if key in overrides:
        return overrides[key]

    text = _norm(_strip_html(f"{name} {description}"))
    matches: List[Tuple[str, str]] = []
    for label, status, rx in _ability_patterns():
        if re.search(rx, text, flags=re.IGNORECASE):
            matches.append((label, status))
    if not matches:
        return ("Not implemented", "")

    status = "Supported" if all(s == "Supported" for _, s in matches) else "Partial"
    notes = ", ".join(sorted({label for label, _ in matches}, key=str.lower))

    extra_markers = [
        " but ",
        " instead ",
        " unless ",
        " except ",
        " however ",
        " only ",
        " while ",
        " after ",
        " before ",
        " until ",
        " at the start",
        " start of",
        " each time",
        " choose ",
        " select ",
        " one of",
        " following",
        ":",
    ]
    if status == "Supported" and any(m in f" {text} " for m in extra_markers):
        status = "Partial"
        notes = f"{notes} (extra conditions not fully modeled)"
    return (status, notes)

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
    }
    if enh_id in explicit:
        return ("Supported", explicit[enh_id])

    status, notes = classify_enhancement_support(description)
    if status == "Supported":
        return (status, notes)
    return (status, notes)


def _stratagem_support(name: str) -> Tuple[str, str, str]:
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
        "BLOOD OFFERING": "Sticky objective on unit destruction; Berzerker Warband only.",
        "UNBOUND ARROGANCE": "Coterie of the Conceited pledge increases by 1 (once per battle round).",
    }

    if name_u in IMPLEMENTED_STRATAGEM_NAMES:
        return ("Implemented", notes.get(name_u, "Implemented in engine."), name_u)
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


def _row(cells: Sequence[str], status: str) -> str:
    color = _status_color(status)
    tds = "".join(f"<td bgcolor=\"{color}\">{c}</td>" for c in cells)
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


def _build_datasheet_map() -> Dict[str, dict]:
    raw = _read_json(os.path.join(WAHA_DIR, "Datasheets.json"))
    out = {}
    for ds in raw:
        did = ds.get("id", "") or ""
        if not did:
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


def _summary_color(supported: int, total: int) -> str:
    if total <= 0:
        return STATUS_COLORS["not implemented"]
    if supported <= 0:
        return STATUS_COLORS["not implemented"]
    if supported >= total:
        return STATUS_COLORS["supported"]
    return STATUS_COLORS["partial"]


def _summary_span(title: str, supported: int, total: int) -> str:
    color = _summary_color(supported, total)
    label = f"{_escape(title)} ({supported} out of {total} abilities supported)"
    return f"<span style=\"background-color:{color}; padding:2px 6px; display:block;\">{label}</span>"


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


def _build_matrix() -> str:
    abilities = _read_json(os.path.join(WAHA_DIR, "Abilities.json"))
    det_abilities_rows = _read_json(os.path.join(WAHA_DIR, "Detachment_abilities.json"))
    ds_abilities_rows = _read_json(os.path.join(WAHA_DIR, "Datasheets_abilities.json"))
    ds_det_rows = _read_json(os.path.join(WAHA_DIR, "Datasheets_detachment_abilities.json"))
    enhancements = _read_json(os.path.join(WAHA_DIR, "Enhancements.json"))
    stratagems = _read_json(os.path.join(WAHA_DIR, "Stratagems.json"))
    detachments = _load_detachments()
    ds_map = _build_datasheet_map()

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

    datasheet_abilities_by_faction: Dict[str, set[str]] = {}
    for row in ds_abilities_rows:
        ability_id = str(row.get("ability_id", "") or "").strip()
        if not ability_id:
            continue
        dsid = str(row.get("datasheet_id", "") or "").strip()
        ds = ds_map.get(dsid)
        if not ds:
            continue
        fid = str(ds.get("faction_id", "") or "").strip().upper()
        if fid not in SUPPORTED_FACTION_IDS:
            continue
        datasheet_abilities_by_faction.setdefault(fid, set()).add(ability_id)

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
        status, notes = _classify_ability(name, desc)
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
    for s in core_strats:
        status, notes, _ = _stratagem_support(s.get("name", ""))
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
            "",
            "### Core Stratagems",
            core_strat_table,
        ]
    )
    lines.append(_details_raw(_summary_span("Core", core_supported, core_total), core_body))
    lines.append("")

    # ---------------- Faction sections ----------------
    for faction_id, meta in FACTION_RULE_METADATA.items():
        if faction_id not in SUPPORTED_FACTION_IDS:
            continue
        faction_name = str(meta.get("faction_name", "") or faction_id)
        faction_items: List[Tuple[str, str]] = []
        faction_body: List[str] = []

        # Army rules
        army_rule_rows = []
        for rule_name in list(meta.get("army_rules", []) or []):
            entry = _ability_entry_by_name(abilities, rule_name, faction_id=faction_id)
            desc = entry.get("description", "") if entry else ""
            status, notes = _classify_ability(rule_name, desc)
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
            faction_body.append("### Army Rules")
            faction_body.append(_table(["Status", "Army Rule", "Description"], army_rule_rows))
            faction_body.append("")

        # Mustering restrictions
        restriction_rows = []
        for restriction in list(meta.get("restrictions", []) or []):
            status, notes = _classify_ability(restriction, "")
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
            faction_body.append("### Mustering Restrictions")
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
            faction_body.append("### Detachments")
            for det in dets:
                det_name = str(det.get("name", "") or "Detachment")
                det_id = str(det.get("id", "") or "").strip()
                det_body: List[str] = []

                # Detachment abilities
                det_ability_rows = []
                det_restrictions: List[str] = []
                for ability in det_abilities_by_det.get(det_id, []):
                    name = ability.get("name", "") or ""
                    desc = ability.get("description", "") or ""
                    status, notes = _classify_ability(name, desc)
                    faction_items.append((status, name))
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
                if det_restrictions:
                    det_restriction_rows = []
                    for restriction in det_restrictions:
                        status, notes = _classify_ability(restriction, "")
                        rules_text, engine_text = _restriction_rule_and_engine(restriction, abilities, faction_id)
                        faction_items.append((status, restriction))
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
                det_enh = enh_by_det.get(det_id, [])
                if det_enh:
                    enh_rows = []
                    for enh in det_enh:
                        name = enh.get("name", "") or ""
                        desc = enh.get("description", "") or ""
                        enh_id = str(enh.get("id", "") or "")
                        status, notes = _enhancement_support(name, enh_id, desc)
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
                det_strats = strats_by_det.get(det_id, [])
                if det_strats:
                    det_strats.sort(key=lambda s: _norm(s.get("name", "")))
                    strat_rows = []
                    for s in det_strats:
                        status, notes, _ = _stratagem_support(s.get("name", ""))
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

        # Datasheet abilities
        ds_ability_rows = []
        ability_ids = sorted(
            datasheet_abilities_by_faction.get(faction_id, set()),
            key=lambda a: _norm(abilities_by_id.get(a, {}).get("name", a)),
        )
        for ability_id in ability_ids:
            entry = abilities_by_id.get(ability_id)
            if not entry:
                continue
            name = entry.get("name", "") or ""
            if not name:
                continue
            desc = entry.get("description", "") or ""
            status, notes = _classify_ability(name, desc)
            faction_items.append((status, name))
            units = _collect_units_for_ability(ability_id, ds_abilities_rows, ds_map, faction_id=faction_id)
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
            faction_body.append("### Datasheet Abilities")
            faction_body.append(_table(["Status", "Ability", "Units", "Description"], ds_ability_rows))
            faction_body.append("")

        supported, total = _summarize_section_count(faction_items)
        faction_section = _details_raw(_summary_span(faction_name, supported, total), "\n".join(faction_body))
        lines.append(faction_section)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    os.makedirs(DOCS_DIR, exist_ok=True)
    content = _build_matrix()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
